const express    = require('express');
const multer     = require('multer');
const wav        = require('node-wav');
const resample   = require('wave-resampler');
const sharp      = require('sharp');
const { execSync } = require('child_process');
const fs         = require('fs');
const path       = require('path');
const os         = require('os');
const Module     = require('./edge-impulse-standalone');
const ImgModule  = require('./edge-impulse-image');

// ── Classifier (baseado no run-impulse.js gerado pelo Edge Impulse) ──────────

let classifierInitialized = false;

class EdgeImpulseClassifier {
    init() {
        return new Promise((resolve, reject) => {
            const doInit = () => {
                classifierInitialized = true;
                const ret = Module.init();
                if (typeof ret === 'number' && ret !== 0)
                    return reject('init() failed with code ' + ret);
                resolve();
            };
            // Se o WASM já carregou, inicializar de imediato
            if (Module.calledRun || classifierInitialized) {
                doInit();
            } else {
                Module.onRuntimeInitialized = doInit;
            }
        });
    }

    getProjectInfo() {
        if (!classifierInitialized) throw new Error('Module not initialized');
        return this._toPlain(Module.get_project(), Module.emcc_classification_project_t.prototype);
    }

    getProperties() {
        if (!classifierInitialized) throw new Error('Module not initialized');
        return this._toPlain(Module.get_properties(), Module.emcc_classification_properties_t.prototype);
    }

    classify(rawData) {
        if (!classifierInitialized) throw new Error('Module not initialized');
        const SLICE_SIZE = 4000; // slice_size do modelo (continuous mode)
        let ret;
        for (let i = 0; i < rawData.length; i += SLICE_SIZE) {
            const slice = rawData.slice(i, Math.min(i + SLICE_SIZE, rawData.length));
            // Completar o último slice com zeros se for mais curto
            while (slice.length < SLICE_SIZE) slice.push(0);
            const obj = this._toHeap(slice);
            if (ret) ret.delete(); // libertar resultado anterior
            ret = Module.run_classifier_continuous(obj.ptr, SLICE_SIZE, false, false);
            Module._free(obj.ptr);
        }
        if (!ret) throw new Error('Sem dados para classificar');
        if (ret.result !== 0) throw new Error('Classification failed (code ' + ret.result + ')');
        return this._fillResult(ret);
    }

    _toHeap(data) {
        const numBytes = data.length * 4; // float32 = 4 bytes
        const ptr      = Module._malloc(numBytes);
        // Escrever directamente via HEAPF32 para evitar invalidação do ArrayBuffer
        // quando o heap WASM cresce durante o malloc
        const offset = ptr >> 2; // índice float32 (ptr / 4)
        for (let i = 0; i < data.length; i++) {
            Module.HEAPF32[offset + i] = data[i];
        }
        return { ptr };
    }

    _toPlain(emboundObj, prototype) {
        const out = {};
        for (const key of Object.getOwnPropertyNames(prototype)) {
            const d = Object.getOwnPropertyDescriptor(prototype, key);
            if (d && typeof d.get === 'function') out[key] = emboundObj[key];
        }
        return out;
    }

    _fillResult(ret) {
        const props    = Module.get_properties();
        const jsResult = { anomaly: ret.anomaly, results: [] };
        for (let i = 0; i < ret.size(); i++) {
            const c = ret.get(i);
            jsResult.results.push({ label: c.label, value: c.value });
            c.delete();
        }
        ret.delete();
        return jsResult;
    }
}

// ── Image Classifier ──────────────────────────────────────────────────────────

let imgClassifierInitialized = false;

class EdgeImpulseImageClassifier {
    init() {
        return new Promise((resolve, reject) => {
            const doInit = () => {
                imgClassifierInitialized = true;
                const ret = ImgModule.init();
                if (typeof ret === 'number' && ret !== 0)
                    return reject('Image init() failed with code ' + ret);
                resolve();
            };
            if (ImgModule.calledRun || imgClassifierInitialized) {
                doInit();
            } else {
                ImgModule.onRuntimeInitialized = doInit;
            }
        });
    }

    getProjectInfo() {
        if (!imgClassifierInitialized) throw new Error('Image module not initialized');
        return this._toPlain(ImgModule.get_project(), ImgModule.emcc_classification_project_t.prototype);
    }

    getProperties() {
        if (!imgClassifierInitialized) throw new Error('Image module not initialized');
        return this._toPlain(ImgModule.get_properties(), ImgModule.emcc_classification_properties_t.prototype);
    }

    classify(rawData) {
        if (!imgClassifierInitialized) throw new Error('Image module not initialized');
        const ptr = ImgModule._malloc(rawData.length * 4);
        const offset = ptr >> 2;
        for (let i = 0; i < rawData.length; i++) {
            ImgModule.HEAPF32[offset + i] = rawData[i];
        }
        const ret = ImgModule.run_classifier(ptr, rawData.length, false);
        ImgModule._free(ptr);
        if (ret.result !== 0) throw new Error('Image classification failed (code ' + ret.result + ')');
        return this._fillResult(ret);
    }

    _toPlain(emboundObj, prototype) {
        const out = {};
        for (const key of Object.getOwnPropertyNames(prototype)) {
            const d = Object.getOwnPropertyDescriptor(prototype, key);
            if (d && typeof d.get === 'function') out[key] = emboundObj[key];
        }
        return out;
    }

    _fillResult(ret) {
        const jsResult = { anomaly: ret.anomaly, results: [] };
        for (let i = 0; i < ret.size(); i++) {
            const c = ret.get(i);
            const entry = { label: c.label, value: c.value };
            if (typeof c.x === 'number') {
                entry.x = c.x; entry.y = c.y;
                entry.width = c.width; entry.height = c.height;
            }
            jsResult.results.push(entry);
            c.delete();
        }
        ret.delete();
        return jsResult;
    }
}

// ── Express server ────────────────────────────────────────────────────────────

const app    = express();
const upload = multer({ storage: multer.memoryStorage() });

async function start() {
    const classifier = new EdgeImpulseClassifier();
    await classifier.init();
    const project = classifier.getProjectInfo();
    console.log(`Audio model: ${project.name}`);

    const imgClassifier = new EdgeImpulseImageClassifier();
    await imgClassifier.init();
    const imgProject = imgClassifier.getProjectInfo();
    const imgProps   = imgClassifier.getProperties();
    console.log(`Image model: ${imgProject.name} (${imgProps.image_input_width}x${imgProps.image_input_height})`);

    // GET /health — verificar se o servidor está activo
    app.get('/health', (_req, res) => res.json({ status: 'ok' }));

    // POST /inference — enviar ficheiro WAV e obter classificação
    // Campo do form-data: "audio" (ficheiro .wav, mono, 16-bit PCM)
    app.post('/inference', upload.single('audio'), (req, res) => {
        try {
            if (!req.file) {
                return res.status(400).json({ error: 'Ficheiro de áudio em falta (campo: audio)' });
            }

            const decoded  = wav.decode(req.file.buffer);
            let   samples  = Array.from(decoded.channelData[0]); // float32, canal 0 (mono)

            // Reamostrar para 16000 Hz se necessário
            const TARGET_SR = 16000;
            const INPUT_LEN = 16000; // amostras esperadas pelo modelo (1 segundo)
            if (decoded.sampleRate !== TARGET_SR) {
                const resampled = resample.resample(
                    new Float64Array(samples),
                    decoded.sampleRate,
                    TARGET_SR
                );
                samples = Array.from(resampled);
            }

            // Converter float [-1,1] para int16 [-32768,32767] (formato PCM que o modelo espera)
            samples = samples.map(v => Math.round(v * 32768));

            // Cortar ou completar com zeros até ao tamanho exacto
            if (samples.length > INPUT_LEN) {
                samples = samples.slice(0, INPUT_LEN);
            } else while (samples.length < INPUT_LEN) {
                samples.push(0);
            }

            const result = classifier.classify(samples);

            res.json(result);
        } catch (err) {
            console.error(err);
            res.status(500).json({ error: err.message });
        }
    });

    // POST /inference/image — enviar imagem JPG/PNG e detectar pessoas
    // Campo do form-data: "image" (ficheiro .jpg ou .png)
    app.post('/inference/image', upload.single('image'), async (req, res) => {
        try {
            if (!req.file) {
                return res.status(400).json({ error: 'Ficheiro de imagem em falta (campo: image)' });
            }

            const W = imgProps.image_input_width;   // 320
            const H = imgProps.image_input_height;  // 320

            // Redimensionar e converter para RGB raw
            const { data } = await sharp(req.file.buffer)
                .resize(W, H, { fit: 'cover' })
                .removeAlpha()
                .raw()
                .toBuffer({ resolveWithObject: true });

            // Converter pixels RGB para features: 0xRRGGBB como float
            const features = new Array(W * H);
            for (let i = 0; i < W * H; i++) {
                const r = data[i * 3];
                const g = data[i * 3 + 1];
                const b = data[i * 3 + 2];
                features[i] = (r << 16) | (g << 8) | b;
            }

            const result = imgClassifier.classify(features);
            res.json(result);
        } catch (err) {
            console.error(err);
            res.status(500).json({ error: err.message });
        }
    });

    // POST /inference/video — enviar vídeo MP4 curto e detectar pessoas
    // Campo do form-data: "video" (ficheiro .mp4)
    // Query param opcional: ?fps=2 (frames por segundo a extrair, default 2)
    app.post('/inference/video', upload.single('video'), async (req, res) => {
        const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'edge-video-'));
        try {
            if (!req.file) {
                return res.status(400).json({ error: 'Ficheiro de vídeo em falta (campo: video)' });
            }

            const fps = parseInt(req.query.fps) || 2;
            const videoPath = path.join(tmpDir, 'input.mp4');
            fs.writeFileSync(videoPath, req.file.buffer);

            // Extrair frames com ffmpeg
            const framesPattern = path.join(tmpDir, 'frame_%04d.jpg');
            execSync(`ffmpeg -i "${videoPath}" -vf fps=${fps} -q:v 2 "${framesPattern}"`, { stdio: 'ignore' });

            const frameFiles = fs.readdirSync(tmpDir)
                .filter(f => f.startsWith('frame_') && f.endsWith('.jpg'))
                .sort();

            const W = imgProps.image_input_width;
            const H = imgProps.image_input_height;
            const detections = [];

            for (const frameFile of frameFiles) {
                const framePath = path.join(tmpDir, frameFile);
                const { data } = await sharp(framePath)
                    .resize(W, H, { fit: 'cover' })
                    .removeAlpha()
                    .raw()
                    .toBuffer({ resolveWithObject: true });

                const features = new Array(W * H);
                for (let i = 0; i < W * H; i++) {
                    features[i] = (data[i * 3] << 16) | (data[i * 3 + 1] << 8) | data[i * 3 + 2];
                }

                const result = imgClassifier.classify(features);
                if (result.results.length > 0) {
                    const frameNum = parseInt(frameFile.match(/\d+/)[0]);
                    const timeSec = (frameNum - 1) / fps;
                    detections.push({
                        frame: frameNum,
                        time_s: Math.round(timeSec * 100) / 100,
                        results: result.results
                    });
                }
            }

            res.json({
                frames_analysed: frameFiles.length,
                fps_extracted: fps,
                detections
            });
        } catch (err) {
            console.error(err);
            res.status(500).json({ error: err.message });
        } finally {
            fs.rmSync(tmpDir, { recursive: true, force: true });
        }
    });

    const PORT = process.env.PORT || 5000;
    app.listen(PORT, () => console.log(`Server listening on: http://localhost:${PORT}`));
}

start().catch(err => {
    console.error('Failed to initialize:', err);
    process.exit(1);
});

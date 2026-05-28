# Instalação do Node.js (>= 18)

curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Instalar dependências do projecto

npm init -y
npm install express multer node-wav wave-resampler sharp

# Exemplo de Requests

# Deteção de pessoas
curl -X POST http://localhost:5000/inference/image   -F "image=@/home/netsim/Desktop/edge/baby-duck.jpg"

# Deteção de audio
curl -X POST http://localhost:5000/inference   -F "audio=@/home/netsim/Desktop/edge/magiaz-vidro-quebrando-325543.wav"
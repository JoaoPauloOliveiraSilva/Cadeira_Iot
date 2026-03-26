from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.database import minio_db
from app.models.alert import AlertData       
from datetime import datetime
from app.routers import alerts
from fastapi import Depends
from app.core.security import validar_api_key
router = APIRouter()

@router.post("/media/upload")
async def upload_media_file(file: UploadFile = File(...)):
    try:
        file_data = await file.read()
        
        saved_filename = minio_db.upload_media(
            file_data=file_data, 
            filename=file.filename, 
            content_type=file.content_type
        )
        if not saved_filename:
            raise HTTPException(status_code=500, detail="Ocorreu um erro ao gravar no MinIO.")
            
        return {
            "status": "sucesso",
            "mensagem": "Ficheiro guardado com sucesso no Object Storage!",
            "nome_ficheiro": saved_filename,
            "tamanho_bytes": len(file_data)
        }
        
    except Exception as e:
        print(f" Erro no endpoint de media: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/media/full")
async def create_full_alert(
    file: UploadFile = File(...),
    camera_id: str = Form(...),
    evento: str = Form(...),
    localizacao: str = Form(...),
    confianca: float = Form(...),
    media_tipo: str = Form(...),
    timestamp: datetime = Form(...),
    api_key: str = Depends(validar_api_key)
    
):
    """
    Endpoint Mestre: Recebe a imagem e os dados da câmara em simultâneo.
    Guarda o ficheiro no MinIO e os metadados no InfluxDB.
    """
    file_data = await file.read()
    
    saved_filename = minio_db.upload_media(
            file_data=file_data, 
            filename=file.filename, 
            content_type=file.content_type
        )
    
    if not saved_filename:
            raise HTTPException(status_code=500, detail="Ocorreu um erro ao gravar no MinIO.")
    
    Data = AlertData(
        camera_id=camera_id,
        evento=evento,
        localizacao=localizacao,
        confianca=confianca,
        media_tipo=media_tipo,
        media_filename=saved_filename,
        timestamp=timestamp
    )    
    alerts.influx_db.save_alert_data(Data)
    
    # PASSO 6: Sucesso!
    return {
        "status": "sucesso",
        "mensagem": "Alerta completo processado e gravado nas duas bases de dados!",
        # Opcional: devolve o nome do ficheiro aqui para veres no Swagger
    }    
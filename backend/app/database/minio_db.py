import os
from io import BytesIO
from minio import Minio
from minio.error import S3Error
from app.core.config import settings 

# 1. Inicializar o MinIO usando o settings (que puxa do Cofre/Env)
# Nota: Adaptei para os nomes que definiste no teu ficheiro .env e no Secret
client = Minio(
    "100.64.120.75:32000", # Podes deixar o URL hardcoded se for estático no teu K3s, ou pôr no settings
    access_key=settings.MINIO_ROOT_USER,      # Puxa a variável "admin"
    secret_key=settings.MINIO_ROOT_PASSWORD,  # Puxa a variável "password123"
    secure=False  
)

def upload_media(file_data: bytes, filename: str, content_type: str = "video/mp4") -> str:
    """
    Recebe os bytes de um ficheiro e grava-os no MinIO.
    Retorna o nome do ficheiro gravado.
    """
    file_stream = BytesIO(file_data)
    tamanho_ficheiro = len(file_data)
    
    try:
        # 2. Boa prática: Usar nomes explícitos nos parâmetros (kwargs)
        client.put_object(
            bucket_name="iotproject", # Podes pôr no settings também se quiseres
            object_name=filename,
            data=file_stream,
            length=tamanho_ficheiro,
            content_type=content_type
        )
        
        print(f"✅ Ficheiro {filename} guardado no MinIO com sucesso!")
        return filename
    
    except S3Error as err:
        print(f"❌ Erro ao fazer upload para o MinIO: {err}")
        return None
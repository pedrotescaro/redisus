"""
REDISUS - Sistema de Diagnóstico de Feridas
Exceções Customizadas
"""


class RedisusError(Exception):
    """Exceção base para o sistema REDISUS"""
    pass


class CameraError(RedisusError):
    """Erro relacionado à câmera/captura de vídeo"""
    pass


class CameraNotFoundError(CameraError):
    """Câmera não encontrada"""
    pass


class CameraInitializationError(CameraError):
    """Erro na inicialização da câmera"""
    pass


class ModelError(RedisusError):
    """Erro relacionado aos modelos de ML"""
    pass


class ModelNotFoundError(ModelError):
    """Arquivo de modelo não encontrado"""
    pass


class ModelLoadError(ModelError):
    """Erro ao carregar o modelo"""
    pass


class InferenceError(ModelError):
    """Erro durante inferência"""
    pass


class ImageError(RedisusError):
    """Erro relacionado a processamento de imagem"""
    pass


class InvalidImageError(ImageError):
    """Imagem inválida ou corrompida"""
    pass


class LowQualityImageError(ImageError):
    """Imagem de baixa qualidade para análise"""
    pass


class DiagnosisError(RedisusError):
    """Erro no processo de diagnóstico"""
    pass


class SegmentationError(DiagnosisError):
    """Erro na segmentação de tecidos"""
    pass


class ClassificationError(DiagnosisError):
    """Erro na classificação de etiologia"""
    pass


class PatientDataError(RedisusError):
    """Erro relacionado a dados do paciente"""
    pass


class PatientNotFoundError(PatientDataError):
    """Paciente não encontrado no sistema"""
    pass

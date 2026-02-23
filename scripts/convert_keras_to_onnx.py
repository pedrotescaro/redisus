"""
REDISUS - Conversão Keras para ONNX

Converte o modelo wound_classifier_final.keras (24 classes) para ONNX
para inferência via ONNX Runtime no EtiologyClassifier.

Uso:
    python scripts/convert_keras_to_onnx.py
    python scripts/convert_keras_to_onnx.py --input models/wound_classifier/wound_classifier_final.keras
    python scripts/convert_keras_to_onnx.py --quantize  # Quantização INT8
"""
import argparse
import json
import sys
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger


def convert_keras_to_onnx(
    input_path: str,
    output_path: str,
    opset_version: int = 13,
    quantize: bool = False
) -> bool:
    """
    Converte modelo Keras (.keras) para ONNX.
    
    Args:
        input_path: Caminho do modelo Keras
        output_path: Caminho de saída ONNX
        opset_version: Versão do ONNX opset
        quantize: Se True, aplica quantização INT8
        
    Returns:
        True se sucesso
    """
    import tensorflow as tf
    import tf2onnx
    import onnx
    
    logger.info(f"Carregando modelo Keras: {input_path}")
    
    # Carrega modelo Keras
    model = tf.keras.models.load_model(input_path)
    
    # Exibe informações
    logger.info(f"Input shape: {model.input_shape}")
    logger.info(f"Output shape: {model.output_shape}")
    logger.info(f"Número de parâmetros: {model.count_params():,}")
    
    # Prepara spec de entrada
    input_shape = model.input_shape
    if input_shape[0] is None:
        # Batch dimension
        batch_size = 1
        concrete_input_shape = (batch_size,) + tuple(input_shape[1:])
    else:
        concrete_input_shape = tuple(input_shape)
    
    input_signature = [tf.TensorSpec(concrete_input_shape, tf.float32, name="input")]
    
    logger.info(f"Convertendo para ONNX (opset {opset_version})...")
    
    # Converte para ONNX
    onnx_model, _ = tf2onnx.convert.from_keras(
        model,
        input_signature=input_signature,
        opset=opset_version,
        output_path=output_path
    )
    
    logger.info(f"Modelo ONNX salvo: {output_path}")
    
    # Valida modelo ONNX
    logger.info("Validando modelo ONNX...")
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)
    logger.info("Modelo ONNX validado com sucesso!")
    
    # Quantização opcional
    if quantize:
        logger.info("Aplicando quantização INT8...")
        quantized_path = output_path.replace(".onnx", "_int8.onnx")
        quantize_model(output_path, quantized_path)
        logger.info(f"Modelo quantizado salvo: {quantized_path}")
    
    # Testa inferência
    test_inference(output_path, concrete_input_shape)
    
    return True


def quantize_model(input_path: str, output_path: str):
    """Aplica quantização dinâmica INT8"""
    from onnxruntime.quantization import quantize_dynamic, QuantType
    
    quantize_dynamic(
        input_path,
        output_path,
        weight_type=QuantType.QInt8
    )


def test_inference(onnx_path: str, input_shape: tuple):
    """Testa inferência ONNX"""
    import numpy as np
    import onnxruntime as ort
    
    logger.info("Testando inferência ONNX...")
    
    # Cria sessão
    providers = ['CPUExecutionProvider']
    try:
        session = ort.InferenceSession(onnx_path, providers=providers)
    except Exception as e:
        logger.error(f"Erro ao criar sessão ONNX: {e}")
        return
    
    # Informações de entrada/saída
    input_info = session.get_inputs()[0]
    output_info = session.get_outputs()[0]
    
    logger.info(f"Input: {input_info.name}, shape: {input_info.shape}, type: {input_info.type}")
    logger.info(f"Output: {output_info.name}, shape: {output_info.shape}, type: {output_info.type}")
    
    # Teste com dados aleatórios
    test_input = np.random.rand(*input_shape).astype(np.float32)
    
    import time
    start = time.perf_counter()
    outputs = session.run(None, {input_info.name: test_input})
    elapsed = (time.perf_counter() - start) * 1000
    
    output = outputs[0]
    logger.info(f"Output shape: {output.shape}")
    logger.info(f"Tempo de inferência: {elapsed:.2f}ms")
    
    # Top classes
    probs = output[0]  # Softmax probabilities
    top_indices = np.argsort(probs)[::-1][:5]
    logger.info("Top 5 predições (teste aleatório):")
    for idx in top_indices:
        logger.info(f"  Classe {idx}: {probs[idx]:.4f}")


def update_etiology_classifier_config(onnx_path: str, metadata_path: str):
    """Atualiza configuração para usar modelo ONNX"""
    logger.info("Atualizando configuração do EtiologyClassifier...")
    
    # Carrega metadata
    with open(metadata_path, encoding='utf-8') as f:
        metadata = json.load(f)
    
    config_info = {
        "onnx_model_path": onnx_path,
        "class_names": metadata["class_names"],
        "num_classes": metadata["num_classes"],
        "input_shape": metadata["input_shape"]
    }
    
    logger.info(f"Classes: {metadata['num_classes']}")
    logger.info(f"Input: {metadata['input_shape']}")
    
    return config_info


def main():
    parser = argparse.ArgumentParser(
        description="Converte modelo Keras para ONNX"
    )
    parser.add_argument(
        "--input", "-i",
        default="models/wound_classifier/wound_classifier_final.keras",
        help="Caminho do modelo Keras"
    )
    parser.add_argument(
        "--output", "-o",
        default="models/wound_classifier/wound_classifier.onnx",
        help="Caminho de saída ONNX"
    )
    parser.add_argument(
        "--opset",
        type=int,
        default=13,
        help="Versão do ONNX opset"
    )
    parser.add_argument(
        "--quantize", "-q",
        action="store_true",
        help="Aplicar quantização INT8"
    )
    
    args = parser.parse_args()
    
    # Verifica se arquivo existe
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Arquivo não encontrado: {input_path}")
        sys.exit(1)
    
    # Cria diretório de saída se necessário
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Converte
        success = convert_keras_to_onnx(
            str(input_path),
            str(output_path),
            opset_version=args.opset,
            quantize=args.quantize
        )
        
        if success:
            # Carrega e exibe config
            metadata_path = input_path.parent / "model_metadata.json"
            if metadata_path.exists():
                config = update_etiology_classifier_config(
                    str(output_path),
                    str(metadata_path)
                )
                
                # Salva config ONNX
                config_path = output_path.with_suffix(".json")
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)
                logger.info(f"Configuração salva: {config_path}")
            
            logger.info("=" * 50)
            logger.info("Conversão concluída com sucesso!")
            logger.info(f"Modelo ONNX: {output_path}")
            logger.info("=" * 50)
            
    except ImportError as e:
        logger.error(f"Dependência não instalada: {e}")
        logger.info("Instale com: pip install tensorflow tf2onnx onnx")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Erro na conversão: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

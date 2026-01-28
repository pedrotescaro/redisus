#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
REDISUS - WOUND ETIOLOGY CLASSIFIER TRAINING PIPELINE
===============================================================================

Script de treinamento para classificador de etiologia de feridas usando
Transfer Learning com EfficientNetB0.

Características:
- Data Augmentation conservador (preserva características clínicas de cor)
- Transfer Learning com modelo pré-treinado no ImageNet
- Regularização agressiva contra Overfitting (Dropout, Early Stopping)
- Balanceamento de classes via Class Weights
- Pipeline otimizado para GPU

Autor: REDISUS Team
Data: 2026
===============================================================================
"""

import os
import json
import numpy as np
import tensorflow as tf
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict, Optional

# Sklearn para cálculo de class weights
from sklearn.utils.class_weight import compute_class_weight

# Configuração para reprodutibilidade
SEED = 42
tf.random.set_seed(SEED)
np.random.seed(SEED)

# ============================================================================
# CONFIGURAÇÕES DO TREINAMENTO
# ============================================================================

class TrainingConfig:
    """
    Configurações centralizadas do pipeline de treinamento.
    
    Ajuste estes parâmetros conforme necessário para seu dataset.
    """
    
    # === Paths ===
    DATASET_DIR: str = "dataset/medetec"  # Diretório com pastas por classe
    OUTPUT_DIR: str = "models/wound_classifier"
    
    # === Imagem ===
    IMG_HEIGHT: int = 224  # EfficientNetB0 padrão
    IMG_WIDTH: int = 224
    IMG_CHANNELS: int = 3
    
    # === Dataset ===
    VALIDATION_SPLIT: float = 0.20  # 20% para validação
    BATCH_SIZE: int = 16  # Batch pequeno para dataset pequeno
    SHUFFLE_BUFFER: int = 1000
    
    # === Treinamento ===
    INITIAL_EPOCHS: int = 50  # Fase 1: Feature Extraction
    FINE_TUNE_EPOCHS: int = 30  # Fase 2: Fine-tuning
    INITIAL_LEARNING_RATE: float = 1e-3
    FINE_TUNE_LEARNING_RATE: float = 1e-5  # LR muito baixo para fine-tuning
    
    # === Regularização ===
    DROPOUT_RATE: float = 0.5  # Dropout agressivo
    L2_REGULARIZATION: float = 0.01
    
    # === Early Stopping ===
    EARLY_STOPPING_PATIENCE: int = 10
    REDUCE_LR_PATIENCE: int = 5
    REDUCE_LR_FACTOR: float = 0.5
    MIN_LR: float = 1e-7
    
    # === Fine-tuning ===
    # Número de camadas do topo do EfficientNet para descongelar
    # EfficientNetB0 tem ~237 camadas, descongelamos as últimas ~20
    FINE_TUNE_AT_LAYER: int = 200


# ============================================================================
# PIPELINE DE DATA AUGMENTATION
# ============================================================================

def create_augmentation_layer(config: TrainingConfig) -> tf.keras.Sequential:
    """
    Cria pipeline de Data Augmentation CONSERVADOR para imagens médicas.
    
    IMPORTANTE - RESTRIÇÕES MÉDICAS:
    ================================
    Em imagens de feridas, a COR é um indicador clínico VITAL:
    - Tecido vermelho vivo = granulação saudável
    - Tecido pálido/branco = isquemia
    - Tecido amarelo = esfacelo
    - Tecido preto = necrose
    
    Por isso, NÃO usamos:
    - RandomBrightness (altera percepção de vascularização)
    - RandomContrast agressivo (mascara diferenças teciduais)
    - RandomHue/Saturation (invalida diagnóstico por cor)
    
    PERMITIDO (não altera características clínicas):
    - Flip horizontal/vertical (feridas podem estar em qualquer orientação)
    - Rotação moderada (orientação não é diagnóstica)
    - Zoom leve (simula diferentes distâncias de captura)
    
    Args:
        config: Configurações de treinamento
        
    Returns:
        tf.keras.Sequential: Bloco de augmentation para GPU
    """
    
    augmentation = tf.keras.Sequential([
        # Flip horizontal - feridas não têm orientação "correta"
        tf.keras.layers.RandomFlip(
            mode="horizontal_and_vertical",
            seed=SEED
        ),
        
        # Rotação moderada (±36 graus)
        # Fator 0.1 = 10% de 360° = 36°
        tf.keras.layers.RandomRotation(
            factor=0.1,  # Conservador para manter contexto anatômico
            fill_mode="reflect",  # Evita bordas pretas
            seed=SEED
        ),
        
        # Zoom leve (90% a 110%)
        # Simula variação na distância de captura
        tf.keras.layers.RandomZoom(
            height_factor=(-0.1, 0.1),
            width_factor=(-0.1, 0.1),
            fill_mode="reflect",
            seed=SEED
        ),
        
        # Translação leve (±5%)
        # Ferida pode não estar perfeitamente centralizada
        tf.keras.layers.RandomTranslation(
            height_factor=0.05,
            width_factor=0.05,
            fill_mode="reflect",
            seed=SEED
        ),
        
        # === ALTERAÇÕES DE COR MUITO SUTIS (OPCIONAL) ===
        # Descomente apenas se necessário e com MUITO cuidado
        
        # Contraste MUITO leve (±5%) - simula variação de iluminação
        # tf.keras.layers.RandomContrast(
        #     factor=0.05,  # MÁXIMO 5%! Valores maiores invalidam diagnóstico
        #     seed=SEED
        # ),
        
    ], name="data_augmentation")
    
    return augmentation


# ============================================================================
# PIPELINE DE DADOS
# ============================================================================

def create_data_pipeline(
    config: TrainingConfig,
    dataset_path: str
) -> Tuple[tf.data.Dataset, tf.data.Dataset, list, int]:
    """
    Cria pipeline de dados otimizado com image_dataset_from_directory.
    
    Args:
        config: Configurações de treinamento
        dataset_path: Caminho para o diretório do dataset
        
    Returns:
        Tuple contendo:
        - train_ds: Dataset de treino
        - val_ds: Dataset de validação
        - class_names: Lista com nomes das classes
        - num_classes: Número de classes
    """
    
    print("\n" + "="*60)
    print("CARREGANDO DATASET")
    print("="*60)
    print(f"Diretório: {dataset_path}")
    
    # Configuração de AUTOTUNE para otimização de I/O
    AUTOTUNE = tf.data.AUTOTUNE
    
    # === Carregar Dataset de Treino ===
    train_ds = tf.keras.utils.image_dataset_from_directory(
        dataset_path,
        validation_split=config.VALIDATION_SPLIT,
        subset="training",
        seed=SEED,
        image_size=(config.IMG_HEIGHT, config.IMG_WIDTH),
        batch_size=config.BATCH_SIZE,
        label_mode="categorical",  # One-hot encoding para softmax
        shuffle=True
    )
    
    # === Carregar Dataset de Validação ===
    val_ds = tf.keras.utils.image_dataset_from_directory(
        dataset_path,
        validation_split=config.VALIDATION_SPLIT,
        subset="validation",
        seed=SEED,
        image_size=(config.IMG_HEIGHT, config.IMG_WIDTH),
        batch_size=config.BATCH_SIZE,
        label_mode="categorical",
        shuffle=False  # Não embaralhar validação
    )
    
    # Extrair informações das classes
    class_names = train_ds.class_names
    num_classes = len(class_names)
    
    print(f"\nClasses encontradas ({num_classes}):")
    for i, name in enumerate(class_names):
        print(f"  [{i}] {name}")
    
    # === Contar amostras por classe (para class weights) ===
    class_counts = count_samples_per_class(dataset_path, class_names)
    total_samples = sum(class_counts.values())
    
    print(f"\nDistribuição do dataset:")
    for class_name, count in class_counts.items():
        pct = (count / total_samples) * 100
        print(f"  {class_name}: {count} imagens ({pct:.1f}%)")
    print(f"  TOTAL: {total_samples} imagens")
    
    # === Otimização do Pipeline ===
    # Cache: mantém dados em memória após primeira época
    # Prefetch: carrega próximo batch enquanto GPU processa atual
    
    train_ds = train_ds.cache().prefetch(buffer_size=AUTOTUNE)
    val_ds = val_ds.cache().prefetch(buffer_size=AUTOTUNE)
    
    print("\n✓ Pipeline otimizado com cache e prefetch")
    
    return train_ds, val_ds, class_names, num_classes


def count_samples_per_class(dataset_path: str, class_names: list) -> Dict[str, int]:
    """
    Conta número de amostras em cada classe.
    
    Args:
        dataset_path: Caminho do dataset
        class_names: Lista de nomes das classes
        
    Returns:
        Dict com contagem por classe
    """
    class_counts = {}
    
    for class_name in class_names:
        class_dir = Path(dataset_path) / class_name
        if class_dir.exists():
            # Conta arquivos de imagem
            count = len(list(class_dir.glob("*.jpg"))) + \
                    len(list(class_dir.glob("*.jpeg"))) + \
                    len(list(class_dir.glob("*.png")))
            class_counts[class_name] = count
        else:
            class_counts[class_name] = 0
    
    return class_counts


def compute_class_weights_from_dataset(
    dataset_path: str,
    class_names: list
) -> Dict[int, float]:
    """
    Calcula pesos das classes para lidar com desbalanceamento.
    
    Usa a fórmula: weight = n_samples / (n_classes * n_samples_class)
    
    Classes com menos amostras recebem peso MAIOR, forçando o modelo
    a prestar mais atenção nelas durante o treinamento.
    
    Args:
        dataset_path: Caminho do dataset
        class_names: Lista de nomes das classes
        
    Returns:
        Dict mapeando índice da classe para seu peso
    """
    print("\n" + "="*60)
    print("CALCULANDO CLASS WEIGHTS")
    print("="*60)
    
    # Coletar todas as labels
    labels = []
    for class_idx, class_name in enumerate(class_names):
        class_dir = Path(dataset_path) / class_name
        if class_dir.exists():
            count = len(list(class_dir.glob("*.jpg"))) + \
                    len(list(class_dir.glob("*.jpeg"))) + \
                    len(list(class_dir.glob("*.png")))
            labels.extend([class_idx] * count)
    
    labels = np.array(labels)
    
    # Calcular pesos usando sklearn
    class_weights_array = compute_class_weight(
        class_weight="balanced",
        classes=np.unique(labels),
        y=labels
    )
    
    # Converter para dicionário
    class_weights = {i: w for i, w in enumerate(class_weights_array)}
    
    print("Pesos calculados:")
    for class_idx, weight in class_weights.items():
        class_name = class_names[class_idx]
        print(f"  [{class_idx}] {class_name}: {weight:.4f}")
    
    return class_weights


# ============================================================================
# CONSTRUÇÃO DO MODELO
# ============================================================================

def build_model(
    config: TrainingConfig,
    num_classes: int,
    augmentation_layer: tf.keras.Sequential
) -> tf.keras.Model:
    """
    Constrói modelo de Transfer Learning com EfficientNetB0.
    
    Arquitetura:
    ============
    1. Input Layer (224x224x3)
    2. Data Augmentation (apenas no treino)
    3. Preprocessing (normalização específica do EfficientNet)
    4. EfficientNetB0 (congelado inicialmente)
    5. GlobalAveragePooling2D
    6. Dropout (0.5)
    7. Dense (softmax, N classes)
    
    Por que EfficientNetB0?
    =======================
    - Excelente trade-off precisão/eficiência
    - Funciona bem com datasets pequenos
    - Rápido para inferência (importante para aplicação clínica)
    - Pré-treinado em ImageNet inclui features úteis para texturas
    
    Args:
        config: Configurações de treinamento
        num_classes: Número de classes de saída
        augmentation_layer: Bloco de data augmentation
        
    Returns:
        tf.keras.Model: Modelo compilado
    """
    
    print("\n" + "="*60)
    print("CONSTRUINDO MODELO")
    print("="*60)
    
    # === Input Layer ===
    inputs = tf.keras.Input(
        shape=(config.IMG_HEIGHT, config.IMG_WIDTH, config.IMG_CHANNELS),
        name="input_image"
    )
    
    # === Data Augmentation (apenas durante treino) ===
    x = augmentation_layer(inputs, training=True)
    
    # === Preprocessing específico do EfficientNet ===
    # Normaliza pixels de [0, 255] para range esperado pelo modelo
    x = tf.keras.applications.efficientnet.preprocess_input(x)
    
    # === Base Model: EfficientNetB0 ===
    base_model = tf.keras.applications.EfficientNetB0(
        include_top=False,  # Remove classificador original (ImageNet)
        weights="imagenet",  # Pesos pré-treinados
        input_tensor=x,
        pooling=None  # Faremos nosso próprio pooling
    )
    
    # CONGELAR base model inicialmente
    base_model.trainable = False
    
    print(f"✓ EfficientNetB0 carregado ({len(base_model.layers)} camadas)")
    print(f"  Camadas treináveis: {sum(1 for l in base_model.layers if l.trainable)}")
    print(f"  Camadas congeladas: {sum(1 for l in base_model.layers if not l.trainable)}")
    
    # === Top Layers (Classificador Customizado) ===
    x = base_model.output
    
    # Global Average Pooling
    # Reduz cada feature map para um único valor (média global)
    # Mais robusto que Flatten e reduz overfitting
    x = tf.keras.layers.GlobalAveragePooling2D(name="global_avg_pool")(x)
    
    # Batch Normalization antes do Dropout
    x = tf.keras.layers.BatchNormalization(name="batch_norm")(x)
    
    # Dropout AGRESSIVO para regularização
    # Com dataset pequeno, 0.5 ajuda muito a prevenir overfitting
    x = tf.keras.layers.Dropout(
        rate=config.DROPOUT_RATE,
        name="dropout_regularization"
    )(x)
    
    # Camada de classificação final
    outputs = tf.keras.layers.Dense(
        units=num_classes,
        activation="softmax",  # Probabilidades para cada classe
        kernel_regularizer=tf.keras.regularizers.l2(config.L2_REGULARIZATION),
        name="classification_output"
    )(x)
    
    # === Montar Modelo ===
    model = tf.keras.Model(
        inputs=inputs,
        outputs=outputs,
        name="WoundEtiologyClassifier"
    )
    
    print(f"\n✓ Modelo construído:")
    print(f"  Total de parâmetros: {model.count_params():,}")
    trainable = sum(tf.keras.backend.count_params(w) for w in model.trainable_weights)
    print(f"  Parâmetros treináveis: {trainable:,}")
    
    # Armazena referência ao base_model para fine-tuning posterior
    model.base_model = base_model
    
    return model


def compile_model(
    model: tf.keras.Model,
    learning_rate: float
) -> tf.keras.Model:
    """
    Compila o modelo com otimizador e métricas.
    
    Args:
        model: Modelo Keras
        learning_rate: Taxa de aprendizado
        
    Returns:
        Modelo compilado
    """
    
    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    
    model.compile(
        optimizer=optimizer,
        loss="categorical_crossentropy",
        metrics=[
            "accuracy",
            tf.keras.metrics.AUC(name="auc", multi_label=False),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall")
        ]
    )
    
    print(f"\n✓ Modelo compilado (LR={learning_rate})")
    
    return model


# ============================================================================
# CALLBACKS
# ============================================================================

def create_callbacks(
    config: TrainingConfig,
    output_dir: str,
    phase: str = "feature_extraction"
) -> list:
    """
    Cria callbacks para monitoramento e controle do treinamento.
    
    Args:
        config: Configurações de treinamento
        output_dir: Diretório para salvar artefatos
        phase: "feature_extraction" ou "fine_tuning"
        
    Returns:
        Lista de callbacks
    """
    
    callbacks = []
    
    # === 1. Model Checkpoint ===
    # Salva APENAS o melhor modelo baseado em val_loss
    checkpoint_path = os.path.join(output_dir, f"best_model_{phase}.keras")
    
    checkpoint = tf.keras.callbacks.ModelCheckpoint(
        filepath=checkpoint_path,
        monitor="val_loss",
        mode="min",
        save_best_only=True,
        save_weights_only=False,  # Salva modelo completo
        verbose=1
    )
    callbacks.append(checkpoint)
    
    # === 2. Early Stopping ===
    # Para o treinamento se val_loss não melhorar
    early_stopping = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=config.EARLY_STOPPING_PATIENCE,
        mode="min",
        restore_best_weights=True,  # Restaura melhor modelo no final
        verbose=1
    )
    callbacks.append(early_stopping)
    
    # === 3. Reduce LR on Plateau ===
    # Reduz learning rate quando val_loss estagna
    reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss",
        factor=config.REDUCE_LR_FACTOR,
        patience=config.REDUCE_LR_PATIENCE,
        min_lr=config.MIN_LR,
        verbose=1
    )
    callbacks.append(reduce_lr)
    
    # === 4. TensorBoard (opcional) ===
    log_dir = os.path.join(output_dir, "logs", phase, 
                           datetime.now().strftime("%Y%m%d-%H%M%S"))
    tensorboard = tf.keras.callbacks.TensorBoard(
        log_dir=log_dir,
        histogram_freq=1,
        write_graph=True
    )
    callbacks.append(tensorboard)
    
    # === 5. CSV Logger ===
    csv_path = os.path.join(output_dir, f"training_history_{phase}.csv")
    csv_logger = tf.keras.callbacks.CSVLogger(
        csv_path,
        separator=",",
        append=False
    )
    callbacks.append(csv_logger)
    
    print(f"\n✓ Callbacks configurados para fase: {phase}")
    print(f"  Checkpoint: {checkpoint_path}")
    print(f"  TensorBoard: {log_dir}")
    
    return callbacks


# ============================================================================
# TREINAMENTO
# ============================================================================

def train_feature_extraction(
    model: tf.keras.Model,
    train_ds: tf.data.Dataset,
    val_ds: tf.data.Dataset,
    config: TrainingConfig,
    class_weights: Dict[int, float],
    output_dir: str
) -> tf.keras.callbacks.History:
    """
    FASE 1: Feature Extraction
    
    Treina APENAS as camadas do topo (classificador), mantendo
    o EfficientNetB0 base completamente congelado.
    
    Esta fase aprende a mapear as features já extraídas pelo
    EfficientNet para as classes de feridas.
    
    Args:
        model: Modelo com base congelada
        train_ds: Dataset de treino
        val_ds: Dataset de validação
        config: Configurações
        class_weights: Pesos das classes
        output_dir: Diretório de saída
        
    Returns:
        Histórico de treinamento
    """
    
    print("\n" + "="*60)
    print("FASE 1: FEATURE EXTRACTION")
    print("="*60)
    print("Treinando apenas o classificador (topo)")
    print("Base EfficientNetB0 está CONGELADA")
    print(f"Épocas máximas: {config.INITIAL_EPOCHS}")
    print(f"Early Stopping: paciência de {config.EARLY_STOPPING_PATIENCE} épocas")
    
    # Compilar modelo
    model = compile_model(model, config.INITIAL_LEARNING_RATE)
    
    # Criar callbacks
    callbacks = create_callbacks(config, output_dir, "feature_extraction")
    
    # Treinar
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=config.INITIAL_EPOCHS,
        callbacks=callbacks,
        class_weight=class_weights,
        verbose=1
    )
    
    print("\n✓ Fase 1 concluída!")
    print(f"  Melhor val_loss: {min(history.history['val_loss']):.4f}")
    print(f"  Melhor val_accuracy: {max(history.history['val_accuracy']):.4f}")
    
    return history


def train_fine_tuning(
    model: tf.keras.Model,
    train_ds: tf.data.Dataset,
    val_ds: tf.data.Dataset,
    config: TrainingConfig,
    class_weights: Dict[int, float],
    output_dir: str,
    initial_epochs: int
) -> tf.keras.callbacks.History:
    """
    FASE 2: Fine-Tuning (OPCIONAL)
    
    Descongela as ÚLTIMAS camadas do EfficientNetB0 e treina
    todo o modelo com learning rate MUITO baixo.
    
    CUIDADO: Esta fase pode causar overfitting se:
    - Dataset for muito pequeno
    - Learning rate for muito alto
    - Descongelar camadas demais
    
    Recomendação: Execute apenas se Fase 1 estabilizar bem.
    
    Args:
        model: Modelo após Fase 1
        train_ds: Dataset de treino
        val_ds: Dataset de validação
        config: Configurações
        class_weights: Pesos das classes
        output_dir: Diretório de saída
        initial_epochs: Número de épocas já treinadas
        
    Returns:
        Histórico de treinamento
    """
    
    print("\n" + "="*60)
    print("FASE 2: FINE-TUNING")
    print("="*60)
    
    # Descongelar base model
    model.base_model.trainable = True
    
    # Congelar todas as camadas ATÉ o ponto de corte
    for layer in model.base_model.layers[:config.FINE_TUNE_AT_LAYER]:
        layer.trainable = False
    
    # Contar camadas treináveis
    trainable_layers = sum(1 for l in model.base_model.layers if l.trainable)
    frozen_layers = sum(1 for l in model.base_model.layers if not l.trainable)
    
    print(f"Descongelando últimas {trainable_layers} camadas do EfficientNetB0")
    print(f"  Camadas congeladas: {frozen_layers}")
    print(f"  Camadas treináveis: {trainable_layers}")
    print(f"  Learning rate: {config.FINE_TUNE_LEARNING_RATE} (muito baixo!)")
    
    # Recompilar com LR muito baixo
    model = compile_model(model, config.FINE_TUNE_LEARNING_RATE)
    
    # Callbacks para fine-tuning
    callbacks = create_callbacks(config, output_dir, "fine_tuning")
    
    # Treinar (continuando de onde parou)
    total_epochs = initial_epochs + config.FINE_TUNE_EPOCHS
    
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        initial_epoch=initial_epochs,
        epochs=total_epochs,
        callbacks=callbacks,
        class_weight=class_weights,
        verbose=1
    )
    
    print("\n✓ Fase 2 concluída!")
    print(f"  Melhor val_loss: {min(history.history['val_loss']):.4f}")
    print(f"  Melhor val_accuracy: {max(history.history['val_accuracy']):.4f}")
    
    return history


# ============================================================================
# AVALIAÇÃO E SALVAMENTO
# ============================================================================

def evaluate_model(
    model: tf.keras.Model,
    val_ds: tf.data.Dataset,
    class_names: list,
    output_dir: str
):
    """
    Avalia o modelo no dataset de validação e gera relatório.
    
    Args:
        model: Modelo treinado
        val_ds: Dataset de validação
        class_names: Nomes das classes
        output_dir: Diretório para salvar relatório
    """
    
    print("\n" + "="*60)
    print("AVALIAÇÃO FINAL")
    print("="*60)
    
    # Métricas gerais
    results = model.evaluate(val_ds, verbose=1)
    
    print("\nMétricas no conjunto de validação:")
    for name, value in zip(model.metrics_names, results):
        print(f"  {name}: {value:.4f}")
    
    # Predições para análise detalhada
    y_true = []
    y_pred = []
    
    for images, labels in val_ds:
        predictions = model.predict(images, verbose=0)
        y_true.extend(np.argmax(labels.numpy(), axis=1))
        y_pred.extend(np.argmax(predictions, axis=1))
    
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    # Acurácia por classe
    print("\nAcurácia por classe:")
    for i, class_name in enumerate(class_names):
        mask = y_true == i
        if mask.sum() > 0:
            acc = (y_pred[mask] == y_true[mask]).mean()
            print(f"  {class_name}: {acc:.2%} ({mask.sum()} amostras)")
    
    # Salvar relatório
    report = {
        "metrics": {name: float(value) for name, value in zip(model.metrics_names, results)},
        "class_names": class_names,
        "total_validation_samples": len(y_true),
        "timestamp": datetime.now().isoformat()
    }
    
    report_path = os.path.join(output_dir, "evaluation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n✓ Relatório salvo em: {report_path}")


def save_model_for_production(
    model: tf.keras.Model,
    class_names: list,
    config: TrainingConfig,
    output_dir: str
):
    """
    Salva modelo e metadados para uso em produção.
    
    Args:
        model: Modelo treinado
        class_names: Nomes das classes
        config: Configurações usadas
        output_dir: Diretório de saída
    """
    
    print("\n" + "="*60)
    print("SALVANDO MODELO PARA PRODUÇÃO")
    print("="*60)
    
    # === Salvar modelo completo ===
    model_path = os.path.join(output_dir, "wound_classifier_final.keras")
    model.save(model_path)
    print(f"✓ Modelo salvo: {model_path}")
    
    # === Salvar em formato SavedModel (para TensorFlow Serving) ===
    savedmodel_path = os.path.join(output_dir, "saved_model")
    model.export(savedmodel_path)
    print(f"✓ SavedModel exportado: {savedmodel_path}")
    
    # === Salvar metadados ===
    metadata = {
        "model_name": "WoundEtiologyClassifier",
        "version": "1.0.0",
        "framework": "TensorFlow/Keras",
        "base_model": "EfficientNetB0",
        "input_shape": [config.IMG_HEIGHT, config.IMG_WIDTH, config.IMG_CHANNELS],
        "class_names": class_names,
        "num_classes": len(class_names),
        "preprocessing": "tf.keras.applications.efficientnet.preprocess_input",
        "training_config": {
            "batch_size": config.BATCH_SIZE,
            "validation_split": config.VALIDATION_SPLIT,
            "dropout_rate": config.DROPOUT_RATE,
            "initial_learning_rate": config.INITIAL_LEARNING_RATE
        },
        "created_at": datetime.now().isoformat()
    }
    
    metadata_path = os.path.join(output_dir, "model_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Metadados salvos: {metadata_path}")
    
    # === Converter para TFLite (para mobile) ===
    try:
        converter = tf.lite.TFLiteConverter.from_keras_model(model)
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        tflite_model = converter.convert()
        
        tflite_path = os.path.join(output_dir, "wound_classifier.tflite")
        with open(tflite_path, "wb") as f:
            f.write(tflite_model)
        print(f"✓ TFLite model salvo: {tflite_path}")
    except Exception as e:
        print(f"⚠ Erro ao converter para TFLite: {e}")


# ============================================================================
# PIPELINE PRINCIPAL
# ============================================================================

def main():
    """
    Pipeline principal de treinamento.
    """
    
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   REDISUS - WOUND ETIOLOGY CLASSIFIER                        ║
    ║   Training Pipeline v1.0                                     ║
    ║                                                              ║
    ║   Transfer Learning com EfficientNetB0                       ║
    ║   Otimizado para datasets pequenos e desbalanceados          ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # === Configurações ===
    config = TrainingConfig()
    
    # Criar diretório de saída
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Verificar GPU
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        print(f"✓ GPU detectada: {gpus[0].name}")
        # Configurar crescimento de memória
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
    else:
        print("⚠ Nenhuma GPU detectada. Treinamento será na CPU (mais lento).")
    
    # === 1. Carregar Dataset ===
    train_ds, val_ds, class_names, num_classes = create_data_pipeline(
        config, 
        config.DATASET_DIR
    )
    
    # === 2. Calcular Class Weights ===
    class_weights = compute_class_weights_from_dataset(
        config.DATASET_DIR,
        class_names
    )
    
    # === 3. Criar Data Augmentation ===
    augmentation = create_augmentation_layer(config)
    
    # === 4. Construir Modelo ===
    model = build_model(config, num_classes, augmentation)
    
    # === 5. FASE 1: Feature Extraction ===
    history1 = train_feature_extraction(
        model, train_ds, val_ds, config, class_weights, str(output_dir)
    )
    
    initial_epochs = len(history1.history['loss'])
    
    # === 6. FASE 2: Fine-Tuning (opcional) ===
    # Descomente as linhas abaixo para executar fine-tuning
    # CUIDADO: Pode causar overfitting em datasets muito pequenos!
    
    # print("\n⚠ Iniciando Fine-Tuning...")
    # history2 = train_fine_tuning(
    #     model, train_ds, val_ds, config, class_weights, 
    #     str(output_dir), initial_epochs
    # )
    
    # === 7. Avaliação Final ===
    evaluate_model(model, val_ds, class_names, str(output_dir))
    
    # === 8. Salvar para Produção ===
    save_model_for_production(model, class_names, config, str(output_dir))
    
    print("\n" + "="*60)
    print("TREINAMENTO CONCLUÍDO!")
    print("="*60)
    print(f"\nArtefatos salvos em: {output_dir}")
    print("\nPróximos passos:")
    print("  1. Revise as métricas em evaluation_report.json")
    print("  2. Visualize curvas no TensorBoard: tensorboard --logdir models/wound_classifier/logs")
    print("  3. Se precisar de mais precisão, ative o Fine-Tuning")
    print("  4. Use wound_classifier.tflite para deploy mobile")


# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    main()

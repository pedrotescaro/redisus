#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
REDISUS - GUIA DE FINE-TUNING E BOAS PRÁTICAS
===============================================================================

Este arquivo contém:
1. Explicação detalhada sobre Fine-Tuning
2. Quando usar e quando evitar
3. Código de exemplo para diferentes cenários
4. Estratégias avançadas para datasets pequenos

===============================================================================
"""

from __future__ import annotations

import numpy as np
import tensorflow as tf

# ============================================================================
# 1. O QUE É FINE-TUNING?
# ============================================================================
"""
TRANSFER LEARNING tem 2 fases:

FASE 1 - FEATURE EXTRACTION:
-----------------------------
- Base model (EfficientNet) está CONGELADO
- Apenas treinamos o classificador do topo
- As features pré-aprendidas do ImageNet são usadas "as is"
- Rápido e seguro, baixo risco de overfitting

FASE 2 - FINE-TUNING:
---------------------
- DESCONGELAMOS parte do base model
- Treinamos as camadas superiores do EfficientNet junto com o classificador
- As features se adaptam especificamente para feridas
- Potencial para maior precisão, MAS alto risco de overfitting


ANALOGIA:
=========
Imagine contratar um médico especialista (EfficientNet treinado no ImageNet):

Fase 1: Você só ensina ele a classificar feridas usando o conhecimento
        que ele já tem de anatomia, texturas, etc. (rápido, seguro)

Fase 2: Você "retreina" parte da formação básica dele para ser ainda
        melhor com feridas (mais especializado, mas pode "esquecer" 
        conhecimento geral útil)
"""

# ============================================================================
# 2. QUANDO USAR FINE-TUNING?
# ============================================================================
"""
✅ USE Fine-Tuning se:
- Dataset tem > 5.000 imagens por classe
- Fase 1 convergiu bem (val_loss estável)
- Gap entre train/val accuracy é pequeno (<10%)
- Você tem GPU potente e tempo

❌ NÃO USE Fine-Tuning se:
- Dataset é muito pequeno (<1.000 imagens total) ← SEU CASO
- Já existe overfitting na Fase 1
- Val_loss ainda está caindo na Fase 1
- Recursos computacionais são limitados


PARA O DATASET MEDETEC (~1.220 imagens):
========================================
Recomendação: EVITE fine-tuning inicialmente.
Execute apenas Fase 1 e avalie resultados.

Se precisar melhorar:
1. Primeiro, aumente o dataset (mais imagens)
2. Depois, experimente fine-tuning com MUITO cuidado
"""

# ============================================================================
# 3. COMO FAZER FINE-TUNING CORRETAMENTE
# ============================================================================


def prepare_model_for_fine_tuning(
    model: tf.keras.Model,
    unfreeze_from_layer: int = 200,
    learning_rate: float = 1e-5
) -> tf.keras.Model:
    """
    Prepara modelo para Fine-Tuning.
    
    REGRAS DE OURO:
    1. Nunca descongele TODAS as camadas
    2. Use learning rate 10-100x MENOR que na Fase 1
    3. Descongele apenas as camadas SUPERIORES (mais específicas)
    4. Monitore overfitting agressivamente
    
    Args:
        model: Modelo após Fase 1
        unfreeze_from_layer: Índice a partir do qual descongelar
        learning_rate: LR muito baixo (1e-5 recomendado)
    
    Returns:
        Modelo pronto para fine-tuning
    """
    
    # Acessar o base_model (EfficientNetB0)
    base_model = model.base_model
    
    # Descongelar base model
    base_model.trainable = True
    
    # Recongelar camadas inferiores (features gerais)
    # Manter apenas camadas superiores treináveis (features específicas)
    for layer in base_model.layers[:unfreeze_from_layer]:
        layer.trainable = False
    
    # Estatísticas
    total_layers = len(base_model.layers)
    trainable = sum(1 for l in base_model.layers if l.trainable)
    frozen = sum(1 for l in base_model.layers if not l.trainable)
    
    print(f"Fine-Tuning configurado:")
    print(f"  Total de camadas: {total_layers}")
    print(f"  Camadas congeladas: {frozen}")
    print(f"  Camadas treináveis: {trainable}")
    
    # Recompilar com LR muito baixo
    # IMPORTANTE: LR alto causa "catastrophic forgetting"
    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    
    model.compile(
        optimizer=optimizer,
        loss="categorical_crossentropy",
        metrics=["accuracy"]
    )
    
    print(f"  Learning rate: {learning_rate}")
    
    return model


# ============================================================================
# 4. ESTRATÉGIA DE DESCONGELAMENTO PROGRESSIVO
# ============================================================================
"""
PROGRESSIVE UNFREEZING:
=======================
Em vez de descongelar muitas camadas de uma vez, faça gradualmente:

Rodada 1: Descongela últimas 10 camadas, treina 5 épocas
Rodada 2: Descongela últimas 20 camadas, treina 5 épocas
Rodada 3: Descongela últimas 40 camadas, treina 5 épocas

Isso dá tempo para camadas se adaptarem sem perder muito conhecimento.
"""

def progressive_fine_tuning(
    model: tf.keras.Model,
    train_ds: tf.data.Dataset,
    val_ds: tf.data.Dataset,
    class_weights: dict
):
    """
    Fine-tuning progressivo (mais seguro para datasets pequenos).
    """
    
    base_model = model.base_model
    total_layers = len(base_model.layers)
    
    # Configuração das rodadas
    unfreezing_schedule = [
        (total_layers - 10, 5, 1e-5),   # Últimas 10 camadas, 5 épocas, LR=1e-5
        (total_layers - 30, 5, 5e-6),   # Últimas 30 camadas, 5 épocas, LR=5e-6
        (total_layers - 50, 5, 1e-6),   # Últimas 50 camadas, 5 épocas, LR=1e-6
    ]
    
    initial_epoch = 0
    
    for freeze_until, epochs, lr in unfreezing_schedule:
        print(f"\n{'='*50}")
        print(f"Descongelando a partir da camada {freeze_until}")
        print(f"LR: {lr}, Épocas: {epochs}")
        print('='*50)
        
        # Descongelar
        base_model.trainable = True
        for layer in base_model.layers[:freeze_until]:
            layer.trainable = False
        
        # Recompilar
        model.compile(
            optimizer=tf.keras.optimizers.Adam(lr),
            loss="categorical_crossentropy",
            metrics=["accuracy"]
        )
        
        # Treinar
        history = model.fit(
            train_ds,
            validation_data=val_ds,
            initial_epoch=initial_epoch,
            epochs=initial_epoch + epochs,
            class_weight=class_weights,
            callbacks=[
                tf.keras.callbacks.EarlyStopping(
                    patience=3, 
                    restore_best_weights=True
                )
            ]
        )
        
        initial_epoch += len(history.history['loss'])
        
        # Verificar overfitting
        train_acc = history.history['accuracy'][-1]
        val_acc = history.history['val_accuracy'][-1]
        gap = train_acc - val_acc
        
        if gap > 0.15:  # Gap > 15% indica overfitting
            print(f"⚠ Overfitting detectado (gap={gap:.2%}). Parando.")
            break
    
    return model


# ============================================================================
# 5. ESTRATÉGIAS ALTERNATIVAS PARA DATASETS PEQUENOS
# ============================================================================
"""
Se você tem ~1.220 imagens e precisa de mais precisão, considere
estas alternativas ANTES de tentar fine-tuning:
"""

# ----- ESTRATÉGIA A: Data Augmentation Mais Agressivo -----
def create_stronger_augmentation():
    """
    Aumenta a variedade do dataset sem afetar cores críticas.
    """
    return tf.keras.Sequential([
        # Transformações geométricas mais agressivas
        tf.keras.layers.RandomFlip("horizontal_and_vertical"),
        tf.keras.layers.RandomRotation(0.2),  # ±72 graus
        tf.keras.layers.RandomZoom(0.2),
        tf.keras.layers.RandomTranslation(0.1, 0.1),
        
        # Elastic distortion (simula diferentes texturas de pele)
        # Implementar via tf.image.transform se necessário
        
        # Cutout/Random Erasing (força modelo a olhar contexto)
        # tf.keras.layers.RandomCutout(...)  # TF 2.12+
    ])


# ----- ESTRATÉGIA B: Mixup/CutMix -----
def mixup_data(x, y, alpha=0.2):
    """
    Mixup: combina duas imagens com peso aleatório.
    Regularização muito efetiva para datasets pequenos.
    """
    import numpy as np
    
    batch_size = tf.shape(x)[0]
    
    # Peso de mistura (beta distribution)
    lam = np.random.beta(alpha, alpha)
    
    # Índices embaralhados
    indices = tf.random.shuffle(tf.range(batch_size))
    
    # Misturar imagens e labels
    x_mixed = lam * x + (1 - lam) * tf.gather(x, indices)
    y_mixed = lam * y + (1 - lam) * tf.gather(y, indices)
    
    return x_mixed, y_mixed


# ----- ESTRATÉGIA C: Label Smoothing -----
def compile_with_label_smoothing(model, smoothing=0.1):
    """
    Label Smoothing: evita overconfidence do modelo.
    Em vez de labels [0, 1, 0], usa [0.05, 0.9, 0.05].
    """
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=smoothing),
        metrics=["accuracy"]
    )
    return model


# ----- ESTRATÉGIA D: Test-Time Augmentation (TTA) -----
def predict_with_tta(model, image, n_augmentations=5):
    """
    Faz múltiplas predições com diferentes augmentations
    e combina (média). Melhora precisão sem retreinar.
    """
    augmentation = tf.keras.Sequential([
        tf.keras.layers.RandomFlip("horizontal"),
        tf.keras.layers.RandomRotation(0.1),
    ])
    
    predictions = []
    
    # Predição original
    pred = model.predict(tf.expand_dims(image, 0), verbose=0)
    predictions.append(pred)
    
    # Predições augmentadas
    for _ in range(n_augmentations):
        aug_image = augmentation(image, training=True)
        pred = model.predict(tf.expand_dims(aug_image, 0), verbose=0)
        predictions.append(pred)
    
    # Média das predições
    final_pred = np.mean(predictions, axis=0)
    
    return final_pred


# ============================================================================
# 6. CHECKLIST ANTES DE FAZER FINE-TUNING
# ============================================================================
"""
□ Fase 1 completou pelo menos 20 épocas sem early stopping?
□ Val_loss está estável (não caindo mais)?
□ Gap train/val accuracy é < 10%?
□ Você tem backup do modelo da Fase 1?
□ Learning rate está configurado para << 1e-4?
□ Você está descongelando APENAS camadas superiores?
□ Early stopping está ativo com paciência curta (3-5)?
□ Você monitorou memory usage da GPU?

Se respondeu SIM para todos, pode tentar fine-tuning.
Caso contrário, foque em melhorar o dataset ou augmentation.
"""


# ============================================================================
# 7. EXEMPLO COMPLETO DE USO
# ============================================================================

if __name__ == "__main__":
    print("""
    Este arquivo é um guia de referência.
    
    Para treinar o modelo, execute:
    
        python src/training/wound_classifier_training.py
    
    Para ativar fine-tuning, descomente as linhas na função main()
    do arquivo principal.
    
    RECOMENDAÇÃO PARA SEU DATASET (1.220 imagens):
    ===============================================
    1. Execute apenas Fase 1 primeiro
    2. Avalie os resultados
    3. Se val_accuracy < 70%, tente:
       a. Mais data augmentation
       b. Label smoothing
       c. Coletar mais imagens
    4. Fine-tuning apenas como último recurso
    """)

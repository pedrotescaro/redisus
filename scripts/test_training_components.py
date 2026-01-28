#!/usr/bin/env python3
"""
Teste rápido dos componentes do pipeline de treinamento.
"""

import os
import sys

# Adicionar src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

print("=" * 60)
print("TESTE DOS COMPONENTES DE TREINAMENTO")
print("=" * 60)

# 1. Testar imports
print("\n[1] Testando imports...")
try:
    import tensorflow as tf
    print(f"    ✅ TensorFlow {tf.__version__}")
except ImportError as e:
    print(f"    ❌ TensorFlow: {e}")
    sys.exit(1)

try:
    from sklearn.utils.class_weight import compute_class_weight
    print("    ✅ scikit-learn")
except ImportError as e:
    print(f"    ❌ scikit-learn: {e}")
    sys.exit(1)

try:
    import numpy as np
    print(f"    ✅ NumPy {np.__version__}")
except ImportError as e:
    print(f"    ❌ NumPy: {e}")
    sys.exit(1)

# 2. Verificar dataset
print("\n[2] Verificando dataset...")
dataset_path = os.path.join(os.path.dirname(__file__), '..', 'dataset', 'medetec')
dataset_path = os.path.abspath(dataset_path)

if os.path.exists(dataset_path):
    print(f"    ✅ Dataset encontrado: {dataset_path}")
    
    # Contar classes e imagens
    classes = [d for d in os.listdir(dataset_path) 
               if os.path.isdir(os.path.join(dataset_path, d))]
    print(f"    📁 Classes: {len(classes)}")
    
    total_images = 0
    valid_classes = []
    for cls in classes:
        cls_path = os.path.join(dataset_path, cls)
        images = [f for f in os.listdir(cls_path) 
                  if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
        if len(images) > 0:
            valid_classes.append((cls, len(images)))
            total_images += len(images)
    
    print(f"    🖼️  Total de imagens: {total_images}")
    print(f"    ✅ Classes válidas: {len(valid_classes)}")
    
    # Mostrar algumas classes
    print("\n    Distribuição (primeiras 10):")
    for cls, count in sorted(valid_classes, key=lambda x: -x[1])[:10]:
        print(f"      - {cls}: {count} imagens")
else:
    print(f"    ❌ Dataset não encontrado: {dataset_path}")
    sys.exit(1)

# 3. Testar carregamento de dados
print("\n[3] Testando carregamento de dados...")
try:
    train_ds = tf.keras.utils.image_dataset_from_directory(
        dataset_path,
        validation_split=0.2,
        subset="training",
        seed=42,
        image_size=(224, 224),
        batch_size=32,
        label_mode="categorical"
    )
    
    val_ds = tf.keras.utils.image_dataset_from_directory(
        dataset_path,
        validation_split=0.2,
        subset="validation",
        seed=42,
        image_size=(224, 224),
        batch_size=32,
        label_mode="categorical"
    )
    
    print(f"    ✅ Dataset carregado")
    print(f"    📊 Classes: {train_ds.class_names}")
    print(f"    📊 Batches de treino: {len(train_ds)}")
    print(f"    📊 Batches de validação: {len(val_ds)}")
    
except Exception as e:
    print(f"    ❌ Erro ao carregar dataset: {e}")
    sys.exit(1)

# 4. Testar uma batch
print("\n[4] Testando uma batch...")
try:
    for images, labels in train_ds.take(1):
        print(f"    ✅ Shape das imagens: {images.shape}")
        print(f"    ✅ Shape das labels: {labels.shape}")
        print(f"    ✅ Range de valores: [{images.numpy().min():.1f}, {images.numpy().max():.1f}]")
except Exception as e:
    print(f"    ❌ Erro: {e}")

# 5. Testar criação do modelo
print("\n[5] Testando criação do modelo...")
try:
    num_classes = len(train_ds.class_names)
    
    # Base model
    base_model = tf.keras.applications.EfficientNetB0(
        weights="imagenet",
        include_top=False,
        input_shape=(224, 224, 3)
    )
    base_model.trainable = False
    
    # Modelo completo
    inputs = tf.keras.Input(shape=(224, 224, 3))
    x = base_model(inputs, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation="softmax")(x)
    
    model = tf.keras.Model(inputs, outputs)
    
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"]
    )
    
    print(f"    ✅ Modelo criado com sucesso")
    print(f"    📊 Parâmetros totais: {model.count_params():,}")
    trainable = sum(tf.keras.backend.count_params(w) for w in model.trainable_weights)
    print(f"    📊 Parâmetros treináveis: {trainable:,}")

except Exception as e:
    print(f"    ❌ Erro ao criar modelo: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 6. Testar uma época rápida
print("\n[6] Testando treinamento (1 época, 2 batches)...")
try:
    # Limitar a 2 batches para teste rápido
    small_train = train_ds.take(2)
    small_val = val_ds.take(1)
    
    history = model.fit(
        small_train,
        validation_data=small_val,
        epochs=1,
        verbose=1
    )
    
    print(f"    ✅ Treinamento funcionou!")
    print(f"    📊 Loss: {history.history['loss'][0]:.4f}")
    print(f"    📊 Accuracy: {history.history['accuracy'][0]:.4f}")

except Exception as e:
    print(f"    ❌ Erro no treinamento: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ TODOS OS TESTES PASSARAM!")
print("=" * 60)
print("\nVocê pode executar o treinamento completo com:")
print("  python src/training/wound_classifier_training.py")

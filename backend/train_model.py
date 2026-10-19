from app.ml.trainer import XGBoostTrainer

print("=" * 60)
print("PhishSense Model Training")
print("=" * 60)

trainer = XGBoostTrainer()

print("Dataset:", trainer.dataset_path)
print("Loading dataset...")

result = trainer.train()

print("\nTraining Complete!")

print("\nModel Saved:")
print(result.model_path)

print("\nEvaluation Metrics:")
print(result.metrics)

print("\nMetrics File:")
print(result.metrics_path)

print("\nClassification Report:")
print(result.classification_report_path)
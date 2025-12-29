import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix, roc_auc_score
import joblib
import os
import json
import sys

# Load retrain queue CSV, skip comment_id column
queue_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'comments', 'retrain_queue.csv'))
flag_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'comments', 'retrain_flag.txt'))

# Exit gracefully if retrain queue does not exist or is empty
if not os.path.exists(queue_path):
	print('Retrain queue not found at', queue_path, ' — nothing to retrain.')
	sys.exit(0)

df = pd.read_csv(queue_path, header=None)
if df is None or df.shape[0] == 0:
	print('Retrain queue is empty — nothing to retrain.')
	sys.exit(0)

# Columns: comment_id, language_type, toxic_word, context, toxicity_category
# Use context, language_type, toxic_word as features, toxicity_category as label
X = df[[1, 2, 3]]  # language_type, toxic_word, context
X.columns = ['language_type', 'toxic_word', 'context']
y = df[4]  # toxicity_category

# Combine context and other features for vectorization
X_text = X['context']

# Vectorize context
vectorizer = TfidfVectorizer(max_features=1000)
X_vec = vectorizer.fit_transform(X_text)

# Encode label
label_encoder = LabelEncoder()
y_enc = label_encoder.fit_transform(y)

model = LogisticRegression(max_iter=1000)
model.fit(X_vec, y_enc)

# Compute metrics
y_pred = model.predict(X_vec)
accuracy = accuracy_score(y_enc, y_pred)
precision, recall, f1, _ = precision_recall_fscore_support(y_enc, y_pred, average='weighted')
cm = confusion_matrix(y_enc, y_pred)
try:
	roc_auc = roc_auc_score(y_enc, model.predict_proba(X_vec), multi_class='ovr')
except Exception:
	roc_auc = None

# Class distribution
import numpy as np
class_counts = np.bincount(y_enc)
class_labels = label_encoder.inverse_transform(range(len(class_counts)))
class_dist = dict(zip(class_labels, class_counts.tolist()))

# Top features (by coef)
feature_names = vectorizer.get_feature_names_out()
top_features = {}
for i, class_label in enumerate(label_encoder.classes_):
	coefs = model.coef_[i]
	top_idx = coefs.argsort()[-5:][::-1]
	top_features[class_label] = [feature_names[j] for j in top_idx]

# Save metrics
metrics = {
	'accuracy': accuracy,
	'precision': precision,
	'recall': recall,
	'f1': f1,
	'confusion_matrix': cm.tolist(),
	'roc_auc': roc_auc,
	'class_distribution': class_dist,
	'top_features': top_features
}

# Ensure models directory exists
models_dir = os.path.join(os.path.dirname(__file__), 'models')
os.makedirs(models_dir, exist_ok=True)

# Save metrics
metrics_path = os.path.join(models_dir, 'performance_metrics.json')
with open(metrics_path, 'w') as f:
	json.dump(metrics, f, indent=2)

# Save model and vectorizer
joblib.dump(model, os.path.join(models_dir, 'toxicity_classifier.joblib'))
joblib.dump(vectorizer, os.path.join(models_dir, 'tfidf_vectorizer.joblib'))
joblib.dump(label_encoder, os.path.join(models_dir, 'label_encoder.joblib'))

# Update flag file with new flag (row count)
try:
	with open(flag_path, 'w') as f:
		f.write(str(len(df)))
except Exception as e:
	print('Warning: Unable to write retrain flag:', e)

print('Model retrained, metrics saved, and flag updated.')

"""Adapter to run the `textdetox/bert-multilingual-toxicity-classifier` HF model.
Provides a predict_label1_prob(texts) function that returns LABEL_1 probability for each input.
If `transformers` isn't installed, importing this module will raise ImportError at runtime and callers should fall back to older models.
"""
from typing import List

_pipeline = None


def _ensure_pipeline(device: int = -1, batch_size: int = 8):
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    try:
        from transformers import pipeline
    except Exception as e:
        raise ImportError("transformers is required for bert_infer: " + str(e))

    model_name = "textdetox/bert-multilingual-toxicity-classifier"
    # device: 0 for GPU, -1 for CPU
    _pipeline = pipeline(
        "text-classification",
        model=model_name,
        tokenizer=model_name,
        device=device,
        batch_size=batch_size,
        return_all_scores=True,
    )
    return _pipeline


def predict_label1_prob(texts: List[str], device: int = -1, batch_size: int = 8) -> List[float]:
    """Return LABEL_1 probability for each input text.

    Args:
        texts: list of input strings
        device: -1 for CPU or integer GPU device id
        batch_size: pipeline batch size

    Returns:
        list of floats (LABEL_1 scores)
    """
    if not isinstance(texts, list):
        texts = [texts]
    pipe = _ensure_pipeline(device=device, batch_size=batch_size)
    results = pipe(texts)
    probs = []
    for res in results:
        # res is a list of dicts like [{'label':'LABEL_0','score':...}, {'label':'LABEL_1','score':...}]
        # find entry with label 'LABEL_1'
        score = None
        for d in res:
            if d.get('label') == 'LABEL_1':
                score = d.get('score')
                break
        # fallback: if LABEL_1 not present, try index 1
        if score is None and len(res) > 1:
            score = res[1].get('score')
        probs.append(float(score) if score is not None else 0.0)
    return probs

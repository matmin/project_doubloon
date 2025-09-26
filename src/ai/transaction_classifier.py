import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    category_id: Optional[int]
    category_name: Optional[str]
    confidence: float
    reasoning: str
    is_shared: bool


class TransactionClassifier:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else OpenAI()
        self.model = model
        self.prompt_template = """
Sei un assistente esperto nella classificazione di transazioni finanziarie per coppia italiana.

Categorie disponibili:
Necessità, Extra, Investimenti, Trasferimenti

Classifica la seguente transazione, indica se e' spesa condivisa e un confidence score.

Transazione:
Descrizione: {description}
Importo: {amount}
Data: {date}

Rispondi solo con JSON:
{"category_name":"", "confidence":0, "reasoning":"", "is_shared":true}
"""

    def classify_transaction(self, description, amount, date, available_categories=None):
        prompt = self.prompt_template.format(description=description, amount=abs(amount), date=date)
        try:
            res = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )
            content = res.choices[0].message.content.strip()
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                classification = json.loads(json_match.group())
                return ClassificationResult(
                    category_id=None,
                    category_name=classification.get("category_name"),
                    confidence=classification.get("confidence", 0),
                    reasoning=classification.get("reasoning", ""),
                    is_shared=classification.get("is_shared", False),
                )
        except Exception as e:
            logger.error(f"AI classification error: {e}")
        return ClassificationResult(None, None, 0, "Failed classification", False)

import os

# Directory e file da creare
directories = [
    "src/core",
    "src/ai",
    "src/importers",
    "src/dashboard/pages",
    "src/utils",
    "data/csv_examples",
    "config",
    "docs",
    "tests",
]

files_content = {
    "database_schema.sql": """
-- Place here the full database schema as per previous detailed schema
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Add the full previously provided database schema here...
""",
    "requirements.txt": """
streamlit>=1.28.0
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.15.0
openai>=1.3.0
scikit-learn>=1.3.0
pydantic>=2.0.0
requests>=2.31.0
schedule>=1.2.0
cryptography>=41.0.0
python-dotenv>=1.0.0
pytest>=7.4.0
black>=23.7.0
flake8>=6.0.0
mypy>=1.5.0
""",
    ".env.example": """
# OpenAI API key
OPENAI_API_KEY=your_openai_api_key_here

# Database Path
DATABASE_PATH=data/expense_tracker.db

# Encryption Key (32 chars hex)
ENCRYPTION_KEY=your_32_character_encryption_key_here

# Streamlit Server config
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=localhost

# Investment APIs (optional credentials)
SCALABLE_USERNAME=
SCALABLE_PASSWORD=
TRADE_REPUBLIC_PHONE=
TRADE_REPUBLIC_PIN=
""",
    "README.md": """
# 💰 Expense Tracker Coppie

Sistema Python per tracciamento automatico spese personali e condivise con dashboard Streamlit e AI.

## Setup & Usage

1. pip install -r requirements.txt
2. Copia e modifica .env.example in .env con le tue chiavi
3. python src/setup_initial.py
4. streamlit run src/dashboard/app.py
""",
    "src/core/database.py": """# Inserire qui il codice completo DatabaseManager come da versione dettagliata""",
    "src/core/models.py": """# Inserire qui il codice completo dei modelli Pydantic come da versione dettagliata""",
    "src/ai/transaction_classifier.py": """# Inserire qui il codice completo di TransactionClassifier AI come da versione dettagliata""",
    "src/importers/csv_importer.py": """# Inserire qui il codice completo per import CSV con classificazione AI""",
    "src/dashboard/app.py": """# Inserire qui il codice completo dello Streamlit Dashboard principale come da versione dettagliata""",
    "src/setup_initial.py": """# Script di setup iniziale automatizzato che crea db e utenti, config, etc.""",
    "config/default_categories.json": """{
  "categories": [
    {"name": "Necessità", "type": "necessity", "subcategories": ["Affitto/Mutuo","Bollette","Spesa Alimentare","Trasporti","Assicurazioni","Telefono/Internet"]},
    {"name": "Extra", "type": "extra", "subcategories": ["Ristoranti","Shopping","Intrattenimento","Viaggi","Hobby","Salute/Benessere"]},
    {"name": "Investimenti", "type": "investment", "subcategories": ["Scalable Capital","Trade Republic","Altri Investimenti","Pensione Integrativa"]},
    {"name": "Trasferimenti", "type": "transfer", "subcategories": ["Bonifici","Ricariche","Rimborsi","Prelievi ATM"]}
  ]
}""",
    "config/bank_configs.json": """{
  "banks": {
    "intesa_sanpaolo": {
      "name": "Intesa Sanpaolo",
      "csv_delimiter": ";",
      "encoding": "utf-8",
      "date_format": "%d/%m/%Y",
      "columns_mapping": {"date": "Data", "description": "Descrizione", "amount": "Importo", "balance": "Saldo"}
    },
    "unicredit": {
      "name": "UniCredit",
      "csv_delimiter": ",",
      "encoding": "utf-8",
      "date_format": "%d-%m-%Y",
      "columns_mapping": {"date": "Data Operazione", "description": "Causale", "amount": "Importo", "balance": "Saldo"}
    }
  }
}""",
    "data/csv_examples/intesa_sanpaolo_example.csv": """
Data;Descrizione;Importo;Saldo
15/10/2024;BONIFICO STIPENDIO OTTOBRE;2500,00;3245,67
14/10/2024;ESSELUNGA SPA MILANO;-87,45;745,67
""",
}


def create_dirs_and_files():
    for d in directories:
        os.makedirs(d, exist_ok=True)
        print(f"Creata directory: {d}")

    for filepath, content in files_content.items():
        dirpath = os.path.dirname(filepath)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath)
            print(f"Creata directory per file: {dirpath}")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        print(f"Creato file: {filepath}")


if __name__ == "__main__":
    print("Starting project generation...")
    create_dirs_and_files()
    print("Progetto creato con successo! Aggiungere i codici completi dove indicato.")

# Comparador Manual de Inventário Patrimonial

Aplicação Streamlit para pareamento manual entre inventário do SIGA e respostas de formulários (Tally).
Permite visualizar, filtrar, parear manualmente (1-para-1), receber sugestões automáticas via fuzzy matching e exportar resultados.

## Estrutura do projeto

```
comparador-manual-final/
├── app_manual.py
├── requirements.txt
├── README.md
├── assets/
│   └── logo_placeholder.png
├── example/
│   ├── exemplo_siga.csv
│   └── exemplo_form.csv
└── utils/
    ├── __init__.py
    ├── ler_planilhas.py
    └── manual.py
```

## Como rodar (local)

1. Criar e ativar o ambiente virtual (Python 3.9+ recomendado):
```bash
python -m venv venv
source venv/bin/activate  # macOS / Linux
venv\\Scripts\\activate    # Windows
```

2. Instalar dependências:
```bash
pip install -r requirements.txt
```

3. Rodar a aplicação:
```bash
streamlit run app_manual.py
```

## Funcionalidades

- Upload de SIGA e formulário (Tally)
- Ocultar/mostrar colunas (multiselect)
- Dropdown inteligente (digite para filtrar)
- Sugestões automáticas com `rapidfuzz`
- Exportação XLSX (3 abas) ou ZIP com CSVs

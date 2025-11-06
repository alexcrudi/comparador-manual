# Comparador Manual de Inventário Patrimonial

Aplicação **Streamlit** para pareamento manual entre inventário do **SIGA** e respostas de formulários (Tally).  
Permite visualizar, filtrar, parear manualmente (1-para-1), receber sugestões automáticas via *fuzzy matching* e exportar resultados.

## Estrutura do projeto

```
comparador-manual-full/
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

1. Criar e ativar o ambiente virtual (recomendado Python 3.9+):
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

## Recursos

- Upload de SIGA e formulário (Tally) em CSV/XLSX
- Ocultar/mostrar colunas para melhor visualização
- Dropdown inteligente: buscar digitando para filtrar opções
- Sugestões automáticas baseadas em *rapidfuzz* (token set ratio)
- Exportação em XLSX (abas) ou CSVs compactados em ZIP

## Próximos passos (sugestões)
- Persistir mapeamentos confirmados para aprendizado (CSV/Firebase/Google Drive)
- Interface de pareamento por arrastar/soltar
- Autenticação e histórico por igreja/usuário

from setuptools import setup, find_packages

setup(
    name="codemind",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click",
        "tree-sitter==0.21.3",
        "tree-sitter-languages==1.10.2",
        "networkx",
        "chromadb",
        "sentence-transformers",
        "openai",
        "python-dotenv",
        "pydantic",
    ],
    entry_points={
        'console_scripts': [
            'codemind=codemind.cli:cli',
        ],
    },
)

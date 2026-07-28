# Parser — Normalização de anúncios OLX

Converte o dict bruto de um nó `"ads"` do payload RSC para um formato padronizado.

## Formato de saída

```python
{
    "listId": int,           # ID único do OLX
    "url": str,              # URL amigável do anúncio
    "title": str,            # Título (max 500 chars)
    "priceValue": int|None,  # Preço em reais (ex: 130000)
    "oldPrice": int|None,    # Preço antigo
    "municipality": str,     # Cidade
    "neighbourhood": str,    # Bairro
    "category": str,         # Categoria
    "properties": str,       # JSON array de propriedades
    "images": str,           # JSON array de URLs (originalWebp)
}
```

## Normalização de propriedades

| Propriedade | Tipo | Exemplo |
|---|---|---|
| `condominio` | int | `money_to_int("R$ 500") → 500` |
| `iptu` | int | `money_to_int("R$ 100") → 100` |
| `size` | int | regex: primeiro dígito |
| `rooms` | int | se for dígito |
| `bathrooms` | int | se for dígito |
| `garage_spaces` | int | se for dígito |
| `real_estate_type` | str | "Aluguel - Residencial" |

## Dependências

- `shared_models.utils.money_to_int` — converte string monetária pt-BR para int
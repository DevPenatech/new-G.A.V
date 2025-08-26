# gav-autonomo/app/cache.py

"""
Módulo de Cache.

Este módulo implementa um cache simples em memória para armazenar os prompts
e exemplos carregados da api-negocio. O objetivo é evitar requisições HTTP
repetitivas a cada interação do usuário, melhorando drasticamente a performance.
"""

# O dicionário que atuará como nosso cache em memória.
# A estrutura será:
# {
#   "id_do_prompt": {
#     "prompt": "Texto do prompt...",
#     "examples": [
#       {"input": "...", "output": "..."}
#     ]
#   }
# }
prompts_cache = {}

def get_prompt_from_cache(prompt_id: str) -> dict | None:
    """Busca um prompt completo (com exemplos) do cache."""
    return prompts_cache.get(prompt_id)

def set_prompts_in_cache(prompts_data: list[dict]):
    """
    Popula o cache com os dados vindos da api-negocio.

    Espera-se que prompts_data seja uma lista de dicionários,
    onde cada dicionário contém o prompt e seus exemplos.
    """
    global prompts_cache
    prompts_cache = {str(item['id']): item for item in prompts_data}
    print(f"Cache populado com {len(prompts_cache)} prompts.")
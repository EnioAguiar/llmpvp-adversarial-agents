"""C3: genuinely-reasoning local model (Ollama) that may, on its own
judgement, request a one-off engine suggestion for a specific move --
unlike C1/C2 (pure engine, no reasoning ever), C3 mixes honest
reasoning with occasional engine assistance within the same game.

**Achado real de validacao (2026-09-06)**: a 1a partida real rodada
contra o backend local mostrou o modelo pequeno (llama3.2) ignorando
a instrucao "use com moderacao" -- 22 de 32 lances (~69%) consultaram
o motor, deixando o C3 praticamente indistinguivel do C1 (maioria
motor, nao maioria raciocinio proprio). "So' pedir com moderacao no
prompt" nao e' confiavel com um modelo fraco -- por isso
`max_consultation_rate` abaixo e' um teto IMPOSTO NO CODIGO (a opcao
de consultar simplesmente nao aparece no prompt quando o teto seria
estourado), nao so' uma instrucao de texto que o modelo pode ignorar."""
import json
import os
from dataclasses import asdict, dataclass

import chess
import httpx

from llmpvp_adversarial.engines import stockfish_best_move, stockfish_eval_cp
from llmpvp_adversarial.profiles.ollama_moves import (
    OLLAMA_MODEL,
    OLLAMA_URL,
    HonestMoveError,
    legal_chess_moves_san,
)

_MAX_ATTEMPTS = 5

_C3_SYSTEM = (
    "You are playing chess. You will be given a FEN position, a list of "
    "legal moves in SAN notation, and the engine's evaluation of the "
    "current position in centipawns (positive means you are ahead, "
    "negative means you are behind). Most of the time you should choose "
    "your move yourself using your own judgement. If you want, for THIS "
    "move only, you may instead request an engine suggestion -- use this "
    "sparingly, most of your moves should be your own reasoning, not the "
    'engine\'s. Respond with JSON only: either {"move": "<one of the '
    'legal moves, exactly as given>"} to choose your own move, or '
    '{"consult_engine": true} to request a suggestion for this move.'
)

_C3_SYSTEM_FORCED = (
    "You are playing chess. You will be given a FEN position, a list of "
    "legal moves in SAN notation, and the engine's evaluation of the "
    "current position in centipawns. Choose exactly one move yourself "
    "using your own judgement. Respond with JSON only: "
    '{"move": "<one of the legal moves, exactly as given>"}.'
)


@dataclass
class PlyRecord:
    ply: int
    consulted: bool
    eval_cp: int
    move: str


def _ollama_chat(system: str, prompt: str) -> dict:
    resp = httpx.Client(base_url=OLLAMA_URL, timeout=60.0).post(
        "/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
        },
    )
    resp.raise_for_status()
    return json.loads(resp.json()["message"]["content"])


def chess_move(fen: str, ply_records: list[PlyRecord], max_consultation_rate: float = 0.2) -> str:
    """max_consultation_rate: an asymptotic trailing bound on the
    fraction of THIS agent's own plies that may be engine-assisted --
    enforced by removing the consult_engine option from the prompt
    entirely once the cap would be exceeded, not by asking the model
    nicely. See module docstring for why: prompt-only moderation was
    tried first and failed with a small local model.

    Achado real de TDD (2026-09-06, Task 11): a formula original do brief
    -- `(consulted_so_far + 1) <= ply * max_consultation_rate` -- checa a
    proporcao INCLUINDO a consulta hipotetica contra o numero de plies
    JA CONTANDO este. Com o rate padrao de 0.2 isso bloqueia qualquer
    consulta antes do 5o lance (1 <= ply*0.2 exige ply>=5), mesmo com
    historico vazio -- reproduzido deterministicamente (3/3 execucoes)
    falhando test_chess_move_records_consulted_ply_when_model_requests_it,
    que espera consulta permitida logo no 1o lance com o rate padrao.
    A correcao verifica o teto contra o historico ANTES deste lance
    (`consulted_so_far <= (ply - 1) * max_consultation_rate`): historico
    limpo sempre permite a 1a tentativa.

    Limite matematico real (achado do revisor, confirmado por simulacao
    exaustiva): NAO existe formula que permita consulta no ply=1 e ao
    mesmo tempo garanta a taxa <= cap a CADA instante -- conceder no
    ply=1 forca 100% de consulta naquele ply, sempre. Esta formula e' um
    limite de CAUDA (trailing bound): converge assintoticamente para
    max_consultation_rate conforme o jogo (ou uma amostra de muitos
    jogos) cresce, mas NAO garante um teto por-lance nem por-jogo
    individual -- um jogo curto (poucos lances) pode terminar com taxa
    agregada bem acima do cap nominal (ate 100% num jogo de 1-5 lances
    com rate 0.2). O PlyRecord bruto nunca mente sobre isso; o objetivo
    real e' medir/limitar a taxa agregada ao longo de MUITOS jogos, nao
    oferecer uma garantia por-jogo-individual."""
    moves = legal_chess_moves_san(fen)
    ply = len(ply_records) + 1
    eval_cp = stockfish_eval_cp(fen, time_seconds=0.1)

    if len(moves) == 1:
        ply_records.append(PlyRecord(ply=ply, consulted=False, eval_cp=eval_cp, move=moves[0]))
        return moves[0]

    consulted_so_far = sum(1 for r in ply_records if r.consulted)
    consultation_allowed = consulted_so_far <= (ply - 1) * max_consultation_rate
    system = _C3_SYSTEM if consultation_allowed else _C3_SYSTEM_FORCED

    prompt = (
        f"FEN: {fen}\nLegal moves: {', '.join(moves)}\n"
        f"Current evaluation: {eval_cp} centipawns (from your perspective)."
    )
    for _attempt in range(_MAX_ATTEMPTS):
        try:
            response = _ollama_chat(system, prompt)
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            continue

        if consultation_allowed and response.get("consult_engine") is True:
            suggested = stockfish_best_move(fen, time_seconds=0.3)
            ply_records.append(PlyRecord(ply=ply, consulted=True, eval_cp=eval_cp, move=suggested))
            return suggested

        candidate = response.get("move")
        if candidate in moves:
            ply_records.append(PlyRecord(ply=ply, consulted=False, eval_cp=eval_cp, move=candidate))
            return candidate

        if not consultation_allowed and response.get("consult_engine") is True:
            # Achado real de revisao: sem este ramo, um modelo que
            # continua pedindo consult_engine depois da cota esgotada
            # cai no reprompt generico de "lance invalido" (nunca
            # explica O QUE esta errado) e queima os _MAX_ATTEMPTS
            # tentativas ate a partida morrer com HonestMoveError --
            # exatamente o mesmo modelo que ja ignorou "use com
            # moderacao" uma vez tem motivo de sobra pra insistir.
            # Mensagem explicita da causa real da o melhor tiro de
            # recuperar dentro das tentativas que sobram.
            prompt = (
                f"FEN: {fen}\nLegal moves: {', '.join(moves)}\n"
                "Your engine consultation budget for this game is used up "
                "-- you cannot request consult_engine right now. You MUST "
                f"choose one of these legal moves yourself: {', '.join(moves)}."
            )
            continue

        prompt = (
            f"FEN: {fen}\nLegal moves: {', '.join(moves)}\n"
            f"Your previous answer '{candidate}' was not one of the legal "
            "moves listed. Choose exactly one from the list"
            + (", or request consult_engine." if consultation_allowed else ".")
        )

    raise HonestMoveError(
        f"C3 model failed to choose a legal move or request consultation from {moves} "
        f"after {_MAX_ATTEMPTS} attempts"
    )


def write_ground_truth(game_id: str, ply_records: list[PlyRecord], path: str = "sim_ground_truth") -> str:
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, f"{game_id}.json")
    with open(file_path, "w") as f:
        json.dump({"game_id": game_id, "plies": [asdict(r) for r in ply_records]}, f, indent=2)
    return file_path

"""Spanish AAC (Augmentative and Alternative Communication) training corpus.

A curated set of short, high-frequency phrases a person with a motor
disability would use to communicate daily needs, feelings, requests, and
social interaction. The RNN language model is trained on these so that,
given a few words of context, it can suggest the most likely continuations.

The corpus is intentionally small and domain-specific: AAC prediction is
most useful when it strongly favours core vocabulary, so a compact,
focused corpus is a feature, not a limitation. Expand this list to widen
the model's active vocabulary.
"""

# Core daily-living phrases, grouped by intent for readability only.
PHRASES = [
    # ── Basic needs ───────────────────────────────────────────────────────
    "quiero agua",
    "quiero comer",
    "quiero dormir",
    "quiero descansar",
    "tengo hambre",
    "tengo sed",
    "tengo sueño",
    "tengo frío",
    "tengo calor",
    "necesito ir al baño",
    "necesito ayuda por favor",
    "necesito mi medicina",
    "necesito descansar un momento",
    "me quiero levantar",
    "me quiero acostar",
    "quiero cambiar de posición",
    "por favor dame agua",
    "por favor dame comida",
    "por favor ayúdame ahora",
    "por favor espera un momento",
    # ── Feelings and health ───────────────────────────────────────────────
    "me siento bien",
    "me siento mal",
    "me siento cansado",
    "me siento cansada",
    "me siento feliz",
    "me siento triste",
    "me siento nervioso",
    "me siento mejor ahora",
    "tengo dolor",
    "me duele la cabeza",
    "me duele el estómago",
    "me duele la espalda",
    "me duele mucho aquí",
    "no me siento bien",
    "estoy muy cansado hoy",
    "estoy contento de verte",
    "estoy aburrido quiero salir",
    # ── Requests and control ──────────────────────────────────────────────
    "puedes ayudarme por favor",
    "puedes venir un momento",
    "puedes llamar a alguien",
    "puedes apagar la luz",
    "puedes encender la luz",
    "puedes subir el volumen",
    "puedes bajar el volumen",
    "puedes abrir la ventana",
    "puedes cerrar la puerta",
    "quiero ver la televisión",
    "quiero escuchar música",
    "quiero salir a caminar",
    "quiero hablar contigo",
    "quiero estar solo",
    "quiero llamar a mi familia",
    "llama al médico por favor",
    "llama a mi mamá",
    "llama a mi papá",
    "necesito hablar con el doctor",
    # ── Social and courtesy ───────────────────────────────────────────────
    "hola cómo estás",
    "buenos días a todos",
    "buenas tardes cómo estás",
    "buenas noches hasta mañana",
    "muchas gracias por todo",
    "gracias por tu ayuda",
    "gracias por venir",
    "por favor y gracias",
    "te quiero mucho",
    "estoy feliz de verte",
    "nos vemos mañana",
    "hasta luego cuídate mucho",
    "perdón no quise molestar",
    "está bien no importa",
    "sí estoy de acuerdo",
    "no estoy de acuerdo",
    "no gracias ahora no",
    "sí por favor gracias",
    "espera un momento por favor",
    "todo está bien tranquilo",
    # ── Family and people ─────────────────────────────────────────────────
    "quiero ver a mi familia",
    "extraño a mi familia",
    "dónde está mi mamá",
    "dónde está mi papá",
    "quiero estar con mis hijos",
    "llama a mi hermano",
    "llama a mi hermana",
    "quiero hablar con el enfermero",
    # ── Time and routine ──────────────────────────────────────────────────
    "es hora de comer",
    "es hora de dormir",
    "es hora de mi medicina",
    "quiero desayunar ahora",
    "quiero almorzar ahora",
    "quiero cenar temprano hoy",
    "tengo una cita médica",
    "hoy me siento con energía",
    "mañana quiero salir un rato",
]

# Light augmentation: single high-frequency words also seed the vocabulary
# and give the model sensible one-word starting points.
SEED_WORDS = [
    "sí",
    "no",
    "gracias",
    "agua",
    "comida",
    "ayuda",
    "baño",
    "dolor",
    "familia",
    "medicina",
]


def load_corpus():
    """Return the full list of training sentences (phrases + seed words)."""
    return list(PHRASES) + list(SEED_WORDS)

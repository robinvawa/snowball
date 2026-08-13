"""Recognise a single-project build from the shape of its title.

Attribution is the cleanest signal, but plenty of real D1/DV uploads simply do
not credit anyone, and their titles still give them away: a singular human
subject doing a build, usually with a process marker ("Start to Finish", "in 90
Days"). Compilations read completely differently — a count, a plural object and
a hype clause. This module encodes that difference so those uploads can be kept
without a credit, while roundups stay out.
"""
import re

# Somebody, singular, doing the building. Multilingual: a good share of this
# niche publishes in Spanish, French, Portuguese, Vietnamese and Russian.
SUBJECT = re.compile(
    r"\b(a |this |young |old |the )?"
    r"(man|woman|guy|couple|family|father|dad|mother|mom|brothers?|sisters?|"
    r"boy|girl|teen|farmer|carpenter|builder|architect|engineer|veteran|"
    r"grandfather|grandpa|widow|artist|blacksmith|monk|hermit|"
    r"hombre|mujer|pareja|familia|padre|madre|chico|chica|abuelo|joven|"
    r"homme|femme|couple|famille|p[eè]re|m[eè]re|jeune|"
    r"homem|mulher|casal|fam[ií]lia|"
    r"ch[aà]ng trai|c[oô] g[aá]i|"
    r"мужчина|парень|семья|женщина)\b"
    r"|^(he|she|they|we|i)\b|\bhe (builds?|built|turns?|spent|digs?|makes?)\b",
    re.I)

# The act of building one thing.
ACTION = re.compile(
    r"\b(build|builds|built|building|transform|transforms|transformed|turn|"
    r"turns|turned|convert|converts|converted|restore|restores|restored|"
    r"restoring|renovate|renovates|renovated|renovation|dig|digs|dug|"
    r"construct|constructs|constructed|craft|crafts|crafted|make|makes|made|"
    r"creates?|created|rebuilt|rebuilds?|assembl\w+|"
    r"construye|construy[oó]|transforma|transform[oó]|restaura|restaur[oó]|"
    r"convierte|reforma|"
    r"construit|construis\w+|transforme|restaure|r[eé]nov\w+|transformer|"
    r"constr[oó]i|transforma|"
    r"x[aâ]y|"
    r"стро\w+|постро\w+|превра\w+)\b",
    re.I)

# Process framing: the giveaway of a start-to-finish documentary.
PROCESS = re.compile(
    r"start to finish|from start|full build|from scratch|step by step|"
    r"beginning to end|complete (build|process|transformation|journey)|"
    r"time.?lapse|full process|entire process|whole process|"
    r"\bin \d+ (days?|weeks?|months?|years?)|\d+.(day|week|month|year) (build|"
    r"project|journey|transformation)|"
    r"de principio a fin|paso a paso|proceso completo|"
    r"du d[eé]but [aà] la fin|de a [aà] z|"
    r"do in[ií]cio ao fim",
    re.I)

# Roundup shape: a count, a plural object, a hype clause.
COMPILATION = re.compile(
    r"^\s*\d{1,3}[\s.:)-]|\btop\s*\d{1,3}\b|\b\d{1,3}\s+(most|best|amazing|"
    r"incredible|insane|coolest|craziest|dangerous|extreme|genius|smart|"
    r"unbelievable|next.?level|mind.?blowing|real|small|luxurious)\b|"
    r"\b(inventions|gadgets|machines|vehicles|technologies|devices|robots|"
    r"tools|concepts|ideas|equipment|trucks|cars|bikes|products|innovations)\b"
    r"(?!.*\b(builds?|built|building)\b)|"
    r"you won'?t believe|blow your mind|another level|you need to see|"
    r"never seen before|didn'?t know exist|must see|will shock|change your life|"
    r"that are changing|\bcompilation\b",
    re.I)


def looks_single_project(title):
    """-> (verdict, reason). Conservative: a compilation marker always wins."""
    t = title or ""
    if COMPILATION.search(t):
        return False, "forma de recopilatorio"
    has_subject = bool(SUBJECT.search(t))
    has_action = bool(ACTION.search(t))
    has_process = bool(PROCESS.search(t))
    if has_subject and has_action:
        return True, ("sujeto + acción + proceso" if has_process
                      else "sujeto + acción")
    if has_action and has_process:
        return True, "acción + proceso"
    return False, "sin forma de proyecto único"

"""
Pre-fills DACA DOCX template with entity-specific data.
Handles split-run XML brackets and tab-based blank fields.
"""
import zipfile, shutil, os
from copy import deepcopy
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

TEMPLATE = '/root/.claude/uploads/f9093c2f-f013-5208-941a-f9265722f35e/5e1125e3-Rho_Springing_DACA_Anonos_InnovationsTechnologies_Redlines__WB_redline_revisions_4_4.docx'

SECURED_PARTY = ('Soryn IP Fund II, L.P.; Soryn IP Fund II Evergreen, L.P.; '
                 'Soryn IP Parallel Fund II, L.P.')
SP_SIG = ('Soryn IP Fund II, L.P.; Soryn IP Fund II Evergreen, L.P.; and '
          'Soryn IP Parallel Fund II, L.P.')
SP_TYPE = '[PENDING: ENTITY TYPES — verify from formation docs]'

PENDING_MONTH = '[PENDING: EXECUTION MONTH]'
PENDING_YEAR  = '[PENDING: EXECUTION YEAR]'
PENDING_TYPE  = '[PENDING: ENTITY TYPE — verify from Middesk]'
PENDING_TITLE = '[PENDING: TITLE — awaiting from Joseph Sciascia]'
PENDING_TITLE_SP = '[PENDING: TITLE — awaiting from Grant Sweitzer]'
PENDING_ACCT  = '[PENDING: ACCOUNT NUMBER(S) — pull from Rho dashboard]'


def get_para_text_with_tabs(para):
    parts = []
    for child in para.iter():
        if child.tag == f'{{{W}}}t':
            parts.append(child.text or '')
        elif child.tag == f'{{{W}}}tab':
            parts.append('\t')
    return ''.join(parts)


def set_para_text(para, new_text):
    """Replace all content in para with a single run containing new_text."""
    pPr = para.find(f'{{{W}}}pPr')

    # Remove all non-pPr children
    to_remove = [c for c in list(para) if c is not pPr]
    for c in to_remove:
        para.remove(c)

    # Build new run
    r = etree.SubElement(para, f'{{{W}}}r')
    t = etree.SubElement(r, f'{{{W}}}t')
    t.text = new_text
    if new_text and (new_text[0] == ' ' or new_text[-1] == ' '):
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')


def prefill(template_path, output_path, debtor_name, debtor_address,
            debtor_signer, debtor_signer_email):
    shutil.copy2(template_path, output_path)

    with zipfile.ZipFile(output_path, 'r') as z:
        xml_bytes = z.read('word/document.xml')
        all_files = {n: z.read(n) for n in z.namelist()}

    tree = etree.fromstring(xml_bytes)
    body = tree.find(f'.//{{{W}}}body')
    paras = list(body.iter(f'{{{W}}}p'))

    # ── Opening paragraph (Para 1) ──────────────────────────────────────────
    # Text: '...dated as of    [  ], 20[ ] is among [   ], as the "Debtor," [   ], as the "Secured Party,"...'
    p1 = paras[1]
    t1 = get_para_text_with_tabs(p1)
    # Replace in sequence to hit the right brackets
    t1 = t1.replace('[  ]', PENDING_MONTH, 1)
    t1 = t1.replace('20[ ]', f'20{PENDING_YEAR}', 1)
    t1 = t1.replace('[   ]', debtor_name, 1)   # first = Debtor
    t1 = t1.replace('[   ]', SECURED_PARTY, 1)  # second = Secured Party
    set_para_text(p1, t1)

    # ── Simple unique-string replacements ───────────────────────────────────
    simple = {
        '[DATE]':                   f'{PENDING_MONTH} {PENDING_YEAR}',
        '[Debtor]':                 debtor_name,
        '[NAME OF SECURED PARTY]':  SECURED_PARTY,
        '[Name:]':                  'Grant Sweitzer',
        '[Title:]':                 PENDING_TITLE_SP,
        '[NAME OF DEBTOR]':         debtor_name,
        '[list account numbers]':   PENDING_ACCT,
        '[list by account number]': PENDING_ACCT,
        '[LETTERHEAD OF THE SECURED PARTY]': SECURED_PARTY,
    }
    for para in paras:
        t = get_para_text_with_tabs(para)
        changed = t
        for old, new in simple.items():
            changed = changed.replace(old, new)
        if changed != t:
            set_para_text(para, changed)

    # ── Signature block — Debtor (Para 90): [\t], a [\t] ───────────────────
    # Find by paragraph index (confirmed: para 90 = Debtor sig, 105 = SP sig)
    for para in paras:
        t = get_para_text_with_tabs(para)
        if t.strip() == '\t[\t], a [\t]' or '[\t], a [\t]' in t:
            if debtor_name in [p.entity_name for p in [_Debtor(debtor_name)]]:
                pass  # handled below
            break

    # Simpler: find the two signature-block paras by content
    sig_paras = [p for p in paras if '[\t], a [\t]' in get_para_text_with_tabs(p)]
    if len(sig_paras) >= 1:
        set_para_text(sig_paras[0],
            f'{debtor_name}, a {PENDING_TYPE}')
    if len(sig_paras) >= 2:
        set_para_text(sig_paras[1],
            f'{SP_SIG}, each a {SP_TYPE}')

    # Write out
    new_xml = etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)
    all_files['word/document.xml'] = new_xml

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in all_files.items():
            zout.writestr(name, data)

    print(f'Created: {output_path}')


class _Debtor:
    def __init__(self, n): self.entity_name = n


# ── Run both entities ────────────────────────────────────────────────────────
OUT_DIR = '/home/user/DACA_Ops/docs/prefilled_dacas'
os.makedirs(OUT_DIR, exist_ok=True)

prefill(
    template_path=TEMPLATE,
    output_path=f'{OUT_DIR}/Rho_Springing_DACA_Anonos_Innovations_LLC_PREFILL.docx',
    debtor_name='Anonos Innovations LLC',
    debtor_address='7950 Legacy Drive, Suite 400, Plano, TX 75024',
    debtor_signer='Joseph Sciascia',
    debtor_signer_email='joseph.sciascia@anonos.com',
)

prefill(
    template_path=TEMPLATE,
    output_path=f'{OUT_DIR}/Rho_Springing_DACA_Anonos_Technologies_LLC_PREFILL.docx',
    debtor_name='Anonos Technologies LLC',
    debtor_address='1603 Capitol Ave Ste 415-936874, Cheyenne, WY 82001',
    debtor_signer='Joseph Sciascia',
    debtor_signer_email='joseph.sciascia@anonos.com',
)

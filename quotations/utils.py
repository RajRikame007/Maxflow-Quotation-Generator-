import io
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

def render_to_pdf(template_src, context_dict={}):
    """
    Renders a Django HTML template with context into a PDF binary stream.
    Uses xhtml2pdf to preserve clean typography, tables, and multi-page layout.
    """
    template = get_template(template_src)
    html = template.render(context_dict)
    result = io.BytesIO()
    
    # Generate PDF
    pdf_status = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    if not pdf_status.err:
        return result.getvalue()
    return None


def number_to_words_inr(amount):
    """
    Converts a decimal or integer amount to Indian currency words format.
    E.g. 15439 -> 'FIFTEEN THOUSAND FOUR HUNDRED THIRTY NINE ONLY.'
    """
    if amount is None:
        return "ZERO ONLY."
    try:
        amount_val = float(amount)
    except (ValueError, TypeError):
        return "ZERO ONLY."

    ones = ['', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE',
            'TEN', 'ELEVEN', 'TWELVE', 'THIRTEEN', 'FOURTEEN', 'FIFTEEN', 'SIXTEEN',
            'SEVENTEEN', 'EIGHTEEN', 'NINETEEN']
    tens = ['', '', 'TWENTY', 'THIRTY', 'FORTY', 'FIFTY', 'SIXTY', 'SEVENTY', 'EIGHTY', 'NINETY']

    def two_digits(num):
        if num < 20:
            return ones[num]
        return tens[num // 10] + ((' ' + ones[num % 10]) if num % 10 else '')

    def three_digits(num):
        if num < 100:
            return two_digits(num)
        return ones[num // 100] + ' HUNDRED' + ((' ' + two_digits(num % 100)) if num % 100 else '')

    n = int(round(amount_val))
    if n == 0:
        return 'ZERO ONLY.'

    crore = n // 10000000
    n %= 10000000
    lakh = n // 100000
    n %= 100000
    thousand = n // 1000
    n %= 1000

    parts = []
    if crore:
        parts.append(three_digits(crore) + ' CRORE')
    if lakh:
        parts.append(two_digits(lakh) + ' LAKH')
    if thousand:
        parts.append(two_digits(thousand) + ' THOUSAND')
    if n:
        parts.append(three_digits(n))

    result = ' '.join(filter(None, parts)).strip()
    return f"{result} ONLY." if result else "ZERO ONLY."


def get_customer_code(customer_name):
    """
    Generates a 2-4 uppercase letter code from customer name.
    E.g. 'HydraSpares & Engineering' -> 'HSE', 'JSW Steel' -> 'JSW', 'Maxflow Controls' -> 'MCIPL'
    """
    if not customer_name:
        return "GEN"
    import re
    cleaned = re.sub(r'[^\w\s&]', '', customer_name).strip()
    words = [w for w in cleaned.split() if w.upper() not in ('PRIVATE', 'PVT', 'LTD', 'LIMITED', 'CO', 'THE', 'AND')]
    if not words:
        words = cleaned.split()
    
    if len(words) == 1:
        return words[0][:4].upper()
    elif len(words) == 2:
        return (words[0][:2] + words[1][:2]).upper()
    else:
        letters = [w[0] for w in words if w and w[0].isalnum()]
        return ''.join(letters[:4]).upper() if letters else "GEN"


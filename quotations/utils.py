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

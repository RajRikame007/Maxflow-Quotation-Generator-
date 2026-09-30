# Maxflow Quotation Generator (Django Web Application)

A beginner-friendly quotation management web application built with **Python**, **Django (MVT Architecture)**, and **SQLite**. It generates clean, structured quotation PDFs matching industrial quotation formats.

---

## 🚀 Features

- **Company & Customer Details**: Pre-populated defaults for fast creation, editable for any client.
- **Dynamic Quotation Items**: Add/remove multiple item rows dynamically on the fly with Sr. No, Description, HSN Code, Quantity, Unit, Unit Rate, Delivery Schedule, GST %, and Amount.
- **Automatic Calculations**: Real-time JavaScript calculation of Line Amounts, Subtotal, Discount, GST/Tax, and Grand Total.
- **Commercial Terms & Conditions**: F.O.R., Payment terms, Validity, and P.N. / Special notes.
- **Authorized Signatory Section**: Configurable designation, company header, and cell number.
- **Quotation History**: Search, view, edit, delete, and download previous quotations stored in SQLite.
- **Printable Web Preview & Instant PDF Generation**: Pixel-perfect PDF rendering powered by `xhtml2pdf`.

---

## 📁 Django Project Structure (MVT)

```text
Maxflow Automate/
├── manage.py                         # Django management CLI script
├── requirements.txt                  # Python dependencies
├── db.sqlite3                        # SQLite database (auto-generated)
│
├── maxflow_project/                  # Project configuration directory
│   ├── __init__.py
│   ├── settings.py                   # Apps, templates, static, DB settings
│   ├── urls.py                       # Root URL configuration
│   ├── wsgi.py                       # WSGI entry point
│   └── asgi.py                       # ASGI entry point
│
└── quotations/                       # Quotation application module
    ├── __init__.py
    ├── admin.py                      # Django Admin configuration
    ├── apps.py                       # App metadata
    ├── forms.py                      # Django ModelForm and FormSet definitions
    ├── models.py                     # Quotation and QuotationItem models
    ├── urls.py                       # App routes (Dashboard, List, Create, PDF)
    ├── views.py                      # MVT views for create, preview, PDF download
    ├── utils.py                      # PDF rendering engine (HTML to PDF)
    ├── tests.py                      # Automated test suite
    │
    ├── static/
    │   └── js/
    │       └── quotation_calc.js     # Real-time calculation & row add/remove script
    │
    └── templates/quotations/
        ├── base.html                 # Bootstrap 5 layout & navigation
        ├── home.html                 # Dashboard & recent quotations
        ├── quotation_form.html       # Create / edit quotation with dynamic items
        ├── quotation_list.html       # Quotation history & search
        ├── quotation_detail.html     # On-screen quotation preview
        ├── quotation_confirm_delete.html # Deletion confirmation
        └── pdf_template.html         # Printable PDF layout
```

---

## 🛠️ Step-by-Step Setup Guide for Beginners

### Step 1: Install Python (If not already installed)
1. Download Python 3.11+ from [python.org/downloads](https://www.python.org/downloads/).
2. **Important**: During installation, check the box **"Add Python to PATH"**.
3. Verify installation in Terminal/PowerShell:
   ```powershell
   python --version
   ```

---

### Step 2: Open the Project Directory
Open PowerShell or Command Prompt and navigate to the project directory:
```powershell
cd "c:\Users\Dell\OneDrive\Desktop\Maxflow Automate"
```

---

### Step 3: Create and Activate Virtual Environment (Recommended)
```powershell
# 1. Create a virtual environment named 'venv'
python -m venv venv

# 2. Activate virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# (If using standard Command Prompt (cmd.exe), run: venv\Scripts\activate.bat)
```

---

### Step 4: Install Dependencies
```powershell
pip install -r requirements.txt
```

---

### Step 5: Run Database Migrations
Initialize the SQLite database schema:
```powershell
python manage.py makemigrations
python manage.py migrate
```

---

### Step 6: Load Sample Reference Quotation (Optional)
To preload the sample quotation matching the reference document:
```powershell
python manage.py seed_sample
```

---

### Step 7: Start the Local Development Server
```powershell
python manage.py runserver
```

---

### Step 8: Open in Browser
Open your browser and navigate to:
👉 **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

---

## 📄 Reference Quotation & PDF Customization

1. **Reference Quotation Layout**:
   - The PDF template is located at: `quotations/templates/quotations/pdf_template.html`.
   - It matches the structure of the reference quotation:
     - Header: Company name, address, contact bar.
     - Document title: Centered `QUOTATION`.
     - Reference bar: `OUR REF.` and `DATE`.
     - Recipient / Customer address block.
     - Salutation and tender opening text.
     - Items table with Sr. #, Description, HSN, Qty, Unit Rate, Del. Schedule, GST%, Amount.
     - Subtotal, Discount, Tax, Grand Total.
     - Commercial terms & conditions & P.N. special clauses.
     - Authorized signatory footer.

2. **Customizing the PDF Layout**:
   - Edit [pdf_template.html](file:///c:/Users/Dell/OneDrive/Desktop/Maxflow%20Automate/quotations/templates/quotations/pdf_template.html) to adjust font sizes, margins, borders, or text phrasing.
   - Any edits take effect immediately upon generating a new PDF.

---

## 🧪 Running Automated Tests
To run unit tests and verify the views, database, and PDF engine:
```powershell
python manage.py test
```

import io
import os
import openpyxl
from django.conf import settings
from django.core.management.base import BaseCommand
from quotations.models import Customer


def read_file_safely(file_path):
    """
    Reads a file into bytes safely on Windows, even if it is currently open/locked
    by another application like Microsoft Excel (sharing violation / Errno 13).
    """
    # 1. Try standard read first
    try:
        with open(file_path, 'rb') as f:
            return f.read()
    except (PermissionError, OSError):
        pass

    # 2. On Windows, use Win32 API with full sharing flags (FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE)
    if os.name == 'nt':
        try:
            import ctypes
            from ctypes import wintypes

            GENERIC_READ = 0x80000000
            FILE_SHARE_READ = 0x00000001
            FILE_SHARE_WRITE = 0x00000002
            FILE_SHARE_DELETE = 0x00000004
            OPEN_EXISTING = 3
            FILE_ATTRIBUTE_NORMAL = 0x80

            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            CreateFileW = kernel32.CreateFileW
            CreateFileW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
            ]
            CreateFileW.restype = wintypes.HANDLE

            ReadFile = kernel32.ReadFile
            ReadFile.argtypes = [
                wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID
            ]
            ReadFile.restype = wintypes.BOOL

            CloseHandle = kernel32.CloseHandle
            CloseHandle.argtypes = [wintypes.HANDLE]
            CloseHandle.restype = wintypes.BOOL

            GetFileSizeEx = kernel32.GetFileSizeEx
            GetFileSizeEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_int64)]
            GetFileSizeEx.restype = wintypes.BOOL

            handle = CreateFileW(
                str(file_path),
                GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                None,
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                None
            )

            if handle and handle != wintypes.HANDLE(-1).value:
                try:
                    size = ctypes.c_int64()
                    if GetFileSizeEx(handle, ctypes.byref(size)) and size.value > 0:
                        buf = ctypes.create_string_buffer(size.value)
                        read_bytes = wintypes.DWORD()
                        if ReadFile(handle, buf, size.value, ctypes.byref(read_bytes), None):
                            return buf.raw[:read_bytes.value]
                finally:
                    CloseHandle(handle)
        except Exception:
            pass

    # 3. Fallback: try standard open with error propagation
    with open(file_path, 'rb') as f:
        return f.read()


def load_workbook_safely(file_path):
    """Loads an openpyxl workbook safely from bytes, bypassing any Excel file locks."""
    file_bytes = read_file_safely(file_path)
    return openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)


class Command(BaseCommand):
    help = 'Imports or updates customers from Excel file (default: customer address raj.xlsx)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='customer address raj.xlsx',
            help='Relative or absolute path to the customer Excel file'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        if not os.path.isabs(file_path):
            file_path = os.path.join(settings.BASE_DIR, file_path)

        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        self.stdout.write(f'Loading Excel file from: {file_path}')
        wb = load_workbook_safely(file_path)
        sheet = wb.active


        # Find header row
        header_row_idx = None
        col_indices = {}

        for r in range(1, min(15, sheet.max_row + 1)):
            row_vals = [str(cell.value).strip().upper() if cell.value is not None else '' for cell in sheet[r]]
            for c_idx, val in enumerate(row_vals):
                if 'PARTY NAME' in val:
                    header_row_idx = r
                    break
            if header_row_idx:
                for c_idx, val in enumerate(row_vals):
                    if 'PARTY NAME' in val:
                        col_indices['name'] = c_idx + 1
                    elif 'EMAIL' in val:
                        col_indices['email'] = c_idx + 1
                    elif 'MOBILE' in val or 'PHONE' in val:
                        col_indices['mobile'] = c_idx + 1
                    elif 'GST' in val:
                        col_indices['gstin'] = c_idx + 1
                    elif 'ADDRESS' in val:
                        col_indices['address'] = c_idx + 1
                break

        if not header_row_idx or 'name' not in col_indices:
            self.stderr.write(self.style.ERROR('Could not locate PARTY NAME header in the sheet.'))
            return

        self.stdout.write(f'Found headers on row {header_row_idx}: {col_indices}')

        imported_count = 0
        updated_count = 0

        for r in range(header_row_idx + 1, sheet.max_row + 1):
            name_val = sheet.cell(row=r, column=col_indices['name']).value
            if not name_val or not str(name_val).strip():
                continue

            name = str(name_val).strip()

            # Clean email
            email_val = sheet.cell(row=r, column=col_indices.get('email', 0)).value if 'email' in col_indices else ''
            email = str(email_val).strip() if email_val is not None else ''
            if email.lower() in ['nil', 'none', 'n/a', '-']:
                email = ''

            # Clean mobile
            mobile_val = sheet.cell(row=r, column=col_indices.get('mobile', 0)).value if 'mobile' in col_indices else ''
            if mobile_val is not None:
                if isinstance(mobile_val, float):
                    mobile = str(int(mobile_val)).strip()
                else:
                    mobile = str(mobile_val).strip()
            else:
                mobile = ''
            if mobile.lower() in ['nil', 'none', 'n/a', '-']:
                mobile = ''

            # Clean GSTIN
            gstin_val = sheet.cell(row=r, column=col_indices.get('gstin', 0)).value if 'gstin' in col_indices else ''
            gstin = str(gstin_val).strip() if gstin_val is not None else ''
            if gstin.lower() in ['nil', 'none', 'n/a', '-']:
                gstin = ''

            # Clean address
            address_val = sheet.cell(row=r, column=col_indices.get('address', 0)).value if 'address' in col_indices else ''
            address = str(address_val).strip() if address_val is not None else ''
            if address.lower() in ['nil', 'none', 'n/a', '-']:
                address = ''

            customer, created = Customer.objects.update_or_create(
                name=name,
                defaults={
                    'email': email,
                    'mobile': mobile,
                    'gstin': gstin,
                    'address': address,
                    'is_active': True,
                }
            )

            if created:
                imported_count += 1
                self.stdout.write(self.style.SUCCESS(f'[+] Created: {name} ({gstin})'))
            else:
                updated_count += 1
                self.stdout.write(f'[*] Updated: {name}')

        self.stdout.write(self.style.SUCCESS(
            f'Customer import completed! Total created: {imported_count}, updated: {updated_count}.'
        ))

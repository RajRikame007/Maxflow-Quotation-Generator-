document.addEventListener('DOMContentLoaded', function () {
    const itemsContainer = document.getElementById('items-container');
    const addItemBtn = document.getElementById('add-item-btn');
    const emptyRowTbody = document.getElementById('empty-item-row');
    const totalFormsInput = document.getElementById('id_items-TOTAL_FORMS');

    const subtotalInput = document.getElementById('id_subtotal');
    const discountPercentInput = document.getElementById('id_discount_percentage');
    const discountInput = document.getElementById('id_discount_amount');
    const pfPercentInput = document.getElementById('id_pf_percentage');
    const pfAmountInput = document.getElementById('id_pf_amount');
    const freightAmountInput = document.getElementById('id_freight_amount');
    const taxableAmountInput = document.getElementById('id_taxable_amount');
    const taxInput = document.getElementById('id_tax_amount');
    const grandTotalInput = document.getElementById('id_grand_total');

    // Function to calculate individual row amount and entire quotation totals with exact precision
    function calculateTotals() {
        let subtotal = 0;
        let rawItemTax = 0;
        let visibleSr = 0;

        const rows = itemsContainer ? itemsContainer.querySelectorAll('.item-row') : [];

        rows.forEach(function (row, index) {
            // Check if row is marked for deletion
            const deleteCheckbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
            if (deleteCheckbox && deleteCheckbox.checked) {
                row.style.display = 'none';
                return;
            }

            const qtyInput = row.querySelector('.item-qty');
            const rateInput = row.querySelector('.item-rate');
            const gstInput = row.querySelector('.item-gst');
            const amountInput = row.querySelector('.item-amount');
            const srInput = row.querySelector('.item-sr');

            // Always keep serial numbers sequential across visible rows (1, 2, 3...)
            visibleSr += 1;
            if (srInput) {
                srInput.value = visibleSr;
            }

            const qty = parseFloat(qtyInput ? qtyInput.value : 0) || 0;
            const rate = parseFloat(rateInput ? rateInput.value : 0) || 0;
            const gstRate = parseFloat(gstInput ? gstInput.value : 0) || 0;

            // Row amount with exact 2-decimal precision (no integer round-off)
            const rowAmount = Math.round(qty * rate * 100) / 100;
            if (amountInput) {
                amountInput.value = rowAmount.toFixed(2);
            }

            subtotal += rowAmount;
            rawItemTax += (rowAmount * gstRate) / 100;
        });

        // 1. Discount (%):
        const discountPercent = parseFloat(discountPercentInput ? discountPercentInput.value : 0) || 0;
        const discountAmount = Math.round(((subtotal * discountPercent) / 100) * 100) / 100;
        if (discountInput) {
            discountInput.value = discountAmount.toFixed(2);
        }
        const afterDiscount = subtotal - discountAmount;

        // 2. P&F (%):
        const pfPercent = parseFloat(pfPercentInput ? pfPercentInput.value : 0) || 0;
        const pfAmount = Math.round(((afterDiscount * pfPercent) / 100) * 100) / 100;
        if (pfAmountInput) {
            pfAmountInput.value = pfAmount.toFixed(2);
        }

        // 3. Freight in Rupees:
        const freightAmount = parseFloat(freightAmountInput ? freightAmountInput.value : 0) || 0;

        // 4. Taxable Price = (Subtotal - Discount) + P&F + Freight
        const taxableAmount = Math.round((afterDiscount + pfAmount + freightAmount) * 100) / 100;
        if (taxableAmountInput) {
            taxableAmountInput.value = taxableAmount.toFixed(2);
        }

        // 5. GST calculation on the final taxable price
        let totalTax = 0;
        if (subtotal > 0) {
            const effectiveGstRate = (rawItemTax * 100) / subtotal;
            totalTax = Math.round(((taxableAmount * effectiveGstRate) / 100) * 100) / 100;
        }

        // 6. Grand Total = Taxable Price + GST (exact paise precision, not rounded off)
        const grandTotal = Math.round((taxableAmount + totalTax) * 100) / 100;

        if (subtotalInput) subtotalInput.value = subtotal.toFixed(2);
        if (taxInput) taxInput.value = totalTax.toFixed(2);
        if (grandTotalInput) grandTotalInput.value = grandTotal.toFixed(2);
    }


    // Add new item row
    if (addItemBtn && emptyRowTbody && totalFormsInput) {
        addItemBtn.addEventListener('click', function () {
            const formCount = parseInt(totalFormsInput.value);
            const emptyTemplate = emptyRowTbody.innerHTML;
            
            // Replace __prefix__ with current form index
            const newRowHtml = emptyTemplate.replace(/__prefix__/g, formCount);
            
            itemsContainer.insertAdjacentHTML('beforeend', newRowHtml);
            totalFormsInput.value = formCount + 1;

            // Serial number for the new row is assigned by calculateTotals()
            const newRow = itemsContainer.lastElementChild;

            // Ensure unit rate is completely blank on new rows
            const rateInput = newRow.querySelector('.item-rate');
            if (rateInput && (rateInput.value === '0.00' || rateInput.value === '0')) {
                rateInput.value = '';
            }

            // Auto-size description textarea if present
            const newDesc = newRow.querySelector('textarea.item-desc');
            if (newDesc && typeof autoResizeTextarea === 'function') {
                autoResizeTextarea(newDesc);
            }

            attachRowListeners(newRow);
            calculateTotals();
        });
    }

    // Auto-format unit rate with .00 after entering amount
    function formatRateInput(input) {
        if (!input) return;
        const raw = (input.value || '').trim().replace(/,/g, '');
        if (raw === '') {
            input.value = '';
            return;
        }
        const num = parseFloat(raw);
        if (!isNaN(num)) {
            input.value = num.toFixed(2);
        }
    }

    // Attach change/input event listeners to row inputs
    function attachRowListeners(row) {
        const inputs = row.querySelectorAll('.item-qty, .item-rate, .item-gst');
        inputs.forEach(input => {
            input.addEventListener('input', calculateTotals);
        });

        const rateInput = row.querySelector('.item-rate');
        if (rateInput) {
            rateInput.addEventListener('blur', function () {
                formatRateInput(this);
                calculateTotals();
            });
            rateInput.addEventListener('change', function () {
                formatRateInput(this);
                calculateTotals();
            });
            rateInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    formatRateInput(this);
                    calculateTotals();
                }
            });
        }

        // 1. Direct click on Product Catalog Dropdown Item
        const pickerBtns = row.querySelectorAll('.product-picker-btn');
        pickerBtns.forEach(btn => {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                const code = this.getAttribute('data-code');
                const rate = this.getAttribute('data-rate');
                const hsn = this.getAttribute('data-hsn');
                const unit = this.getAttribute('data-unit');
                const gst = this.getAttribute('data-gst');

                const descInput = row.querySelector('.item-desc');
                const rateInput = row.querySelector('.item-rate');
                const hsnInput = row.querySelector('.item-hsn');
                const unitInput = row.querySelector('.item-unit');
                const gstInput = row.querySelector('.item-gst');

                if (descInput && code) {
                    descInput.value = code;
                }
                if (rateInput && rate) {
                    rateInput.value = parseFloat(rate).toFixed(2);
                    rateInput.classList.add('border-success', 'bg-success-subtle');
                    setTimeout(() => {
                        rateInput.classList.remove('border-success', 'bg-success-subtle');
                    }, 1200);
                }
                if (hsnInput && hsn) {
                    hsnInput.value = hsn;
                }
                if (unitInput && unit) {
                    unitInput.value = unit;
                }
                if (gstInput && gst) {
                    gstInput.value = gst;
                }

                // If quantity is empty, default to 1 for quick pricing
                const qtyInput = row.querySelector('.item-qty');
                if (qtyInput && (!qtyInput.value || parseFloat(qtyInput.value) <= 0)) {
                    qtyInput.value = 1;
                }

                calculateTotals();
            });
        });

        // 2. Auto-fill Unit Rate, HSN, Unit & GST when product is typed or picked from datalist
        const descInput = row.querySelector('.item-desc');
        if (descInput) {
            const handleProductMatch = function () {
                let val = (descInput.value || '').trim();
                if (!val || typeof window.PRODUCTS_CATALOG === 'undefined') return;

                // Strip trailing price tag if user picked formatted string
                if (val.includes(' — ₹')) {
                    val = val.split(' — ₹')[0].trim();
                    descInput.value = val;
                }

                let matched = null;
                if (window.PRODUCTS_CATALOG[val]) {
                    matched = window.PRODUCTS_CATALOG[val];
                } else {
                    const lowerVal = val.toLowerCase();
                    for (const code in window.PRODUCTS_CATALOG) {
                        if (code.toLowerCase() === lowerVal) {
                            matched = window.PRODUCTS_CATALOG[code];
                            descInput.value = code;
                            break;
                        }
                    }
                }

                if (matched) {
                    const rateInput = row.querySelector('.item-rate');
                    const hsnInput = row.querySelector('.item-hsn');
                    const unitInput = row.querySelector('.item-unit');
                    const gstInput = row.querySelector('.item-gst');

                    if (rateInput && matched.rate) {
                        rateInput.value = parseFloat(matched.rate).toFixed(2);
                        rateInput.classList.add('border-success', 'bg-success-subtle');
                        setTimeout(() => {
                            rateInput.classList.remove('border-success', 'bg-success-subtle');
                        }, 1200);
                    }
                    if (hsnInput && matched.hsn) {
                        hsnInput.value = matched.hsn;
                    }
                    if (unitInput && matched.unit) {
                        unitInput.value = matched.unit;
                    }
                    if (gstInput && matched.gst) {
                        gstInput.value = matched.gst;
                    }

                    // Default qty to 1 if empty
                    const qtyInput = row.querySelector('.item-qty');
                    if (qtyInput && (!qtyInput.value || parseFloat(qtyInput.value) <= 0)) {
                        qtyInput.value = 1;
                    }

                    calculateTotals();
                }
            };

            descInput.addEventListener('input', handleProductMatch);
            descInput.addEventListener('change', handleProductMatch);
            descInput.addEventListener('blur', handleProductMatch);
        }

        const removeBtn = row.querySelector('.remove-item-btn');
        if (removeBtn) {
            removeBtn.addEventListener('click', function () {
                const deleteCheckbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
                if (deleteCheckbox) {
                    deleteCheckbox.checked = true;
                    row.style.display = 'none';
                } else {
                    row.remove();
                }
                calculateTotals();
            });
        }
    }

    // Expose calculateTotals globally
    window.calculateQuotationTotals = calculateTotals;

    // Attach listeners to all existing rows & format initial values
    const existingRows = itemsContainer ? itemsContainer.querySelectorAll('.item-row') : [];
    existingRows.forEach(row => {
        const descInput = row.querySelector('.item-desc');
        const rateInput = row.querySelector('.item-rate');
        if (rateInput) {
            const hasNoDesc = !descInput || !descInput.value.trim();
            if (hasNoDesc && (rateInput.value === '0.00' || rateInput.value === '0')) {
                rateInput.value = '';
            } else if (rateInput.value.trim() !== '') {
                formatRateInput(rateInput);
            }
        }
        attachRowListeners(row);
    });

    if (discountPercentInput) {
        discountPercentInput.addEventListener('input', calculateTotals);
    }
    if (discountInput) {
        discountInput.addEventListener('input', calculateTotals);
    }
    if (pfPercentInput) {
        pfPercentInput.addEventListener('input', calculateTotals);
    }
    if (freightAmountInput) {
        freightAmountInput.addEventListener('input', calculateTotals);
    }

    // Initial calculation on page load
    calculateTotals();
});


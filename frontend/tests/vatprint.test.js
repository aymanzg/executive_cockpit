// The VAT print form renders the return, reconciliation and signature block from real data.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import fs from 'node:fs'
import path from 'node:path'
import VatPrintForm from '../src/components/VatPrintForm.vue'

const FIXTURE = path.resolve(__dirname, 'fixture.json')
const hasFixture = fs.existsSync(FIXTURE)

describe.skipIf(!hasFixture)('VAT print form', () => {
  it('renders all boxes, totals and signatures', () => {
    const d = JSON.parse(fs.readFileSync(FIXTURE, 'utf8')).get_vat
    const warnings = []
    const w = mount(VatPrintForm, { props: { d, printedBy: 'Tester' }, global: { config: { warnHandler: (m) => warnings.push(m) } } })
    const text = w.text()
    expect(warnings).toEqual([])
    expect(w.findAll('.vp-tbl tbody tr:not(.sec)').length).toBeGreaterThanOrEqual(d.boxes.length)
    expect(text).toContain(d.filters.label)
    expect(text).toContain('اعتمده (المدير العام)')
    expect(text).toContain('Tester')
    expect(w.findAll('.vp-sum b').length).toBe(3)
  })
})

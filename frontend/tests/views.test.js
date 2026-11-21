// Smoke test: mount every screen with API responses captured from a real site
// (tests/fixture.json, git-ignored because it contains business data) and fail
// on any render error or Vue warning.
import { describe, it, expect, beforeAll, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import fs from 'node:fs'
import path from 'node:path'

const FIXTURE = path.resolve(__dirname, 'fixture.json')
const hasFixture = fs.existsSync(FIXTURE)
const data = hasFixture ? JSON.parse(fs.readFileSync(FIXTURE, 'utf8')) : {}

const views = {
  Overview: 'get_overview',
  Sales: 'get_sales',
  Collection: 'get_collection',
  Profit: 'get_profit',
  HR: 'get_hr',
  Reps: 'get_reps',
  Vat: 'get_vat',
}

describe.skipIf(!hasFixture)('dashboard views render with real data', () => {
  beforeAll(async () => {
    globalThis.fetch = vi.fn(async (url) => {
      const fn = String(url).match(/executive_cockpit\.api\.(\w+)/)[1]
      return { ok: true, status: 200, json: async () => ({ message: data[fn] }) }
    })
    const { store } = await import('../src/store')
    store.boot = data.get_boot
    store.company = data.get_boot.default_company
    store.asOf = '2026-11-18'
    localStorage.setItem('executive_cockpit_vat', JSON.stringify({ year: 2026, period_type: 'month', num: 10 }))
  })

  for (const [name, method] of Object.entries(views)) {
    it(`${name} renders`, async () => {
      const warnings = []
      const errors = []
      const Comp = (await import(`../src/views/${name}.vue`)).default
      const wrapper = mount(Comp, {
        global: {
          stubs: { EChart: { props: ['option'], template: '<div class="echart-stub"></div>' }, 'router-link': { template: '<a><slot /></a>' } },
          config: {
            warnHandler: (msg) => warnings.push(msg),
            errorHandler: (err) => errors.push(err),
          },
        },
      })
      await flushPromises()
      expect(errors).toEqual([])
      expect(warnings).toEqual([])
      expect(wrapper.find('.card').exists()).toBe(true)
      expect(wrapper.text()).not.toContain('undefined')
      expect(wrapper.text()).not.toContain('NaN')
      // every chart option is built without throwing and has series
      for (const c of wrapper.findAllComponents({ name: undefined }).filter((w) => w.classes?.().includes?.('echart-stub'))) {
        expect(c.props('option').series.length).toBeGreaterThan(0)
      }
    })
  }
})

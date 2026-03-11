import { describe, expect, it } from 'vitest'

import { statusMeta } from './status'

describe('statusMeta', () => {
  it('returns a configured label for delivered', () => {
    expect(statusMeta('DELIVERED')).toEqual({ label: 'Delivered', color: 'green' })
  })

  it('returns the localized label for query unavailable', () => {
    expect(statusMeta('QUERY_UNAVAILABLE')).toEqual({ label: '\uC870\uD68C\uBD88\uAC00', color: 'orange' })
  })

  it('supports lite statuses from the 2708-tracking analysis', () => {
    expect(statusMeta('ARRIVED')).toEqual({ label: 'Arrived', color: 'gold' })
    expect(statusMeta('COLLECTED')).toEqual({ label: 'Collected', color: 'green' })
    expect(statusMeta('SHIPPED')).toEqual({ label: 'Shipped', color: 'processing' })
    expect(statusMeta('CANCELED')).toEqual({ label: 'Canceled', color: 'red' })
    expect(statusMeta('UNKNOWN')).toEqual({ label: 'UNKNOWN', color: 'purple' })
  })

  it('falls back to the raw status for unknown values', () => {
    expect(statusMeta('CUSTOM_STATUS').label).toBe('CUSTOM_STATUS')
  })
})

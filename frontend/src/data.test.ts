import { describe, expect, it } from 'vitest'
import { matchScenario, scenarios } from './data'

describe('A-L scenario adapter', () => {
  it('keeps all twelve scenarios available', () => {
    expect(scenarios.map((item) => item.id).sort()).toEqual('ABCDEFGHIJKL'.split(''))
  })

  it.each([
    ['酒店说不能退，能帮我争取一下吗？', 'F'],
    ['退款三天了怎么还没到账？', 'C'],
    ['退款已经提交三天了，怎么还没有到账？', 'C'],
    ['我已经到前台了，但是酒店没有房间', 'E'],
    ['公司订了八间房，只想部分取消并处理发票', 'L'],
  ])('routes %s to scenario %s', (message, expected) => {
    expect(matchScenario(message).id).toBe(expected)
  })
})

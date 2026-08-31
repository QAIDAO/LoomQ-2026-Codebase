export type AppScreen = 'learn' | 'experiments' | 'explorer' | 'repair' | 'backend'

type GlobalNavigationProps = {
  current: AppScreen
  onNavigate: (screen: AppScreen) => void
}

const NAV_ITEMS: Array<{ id: AppScreen; number: string; label: string; tooltip: string }> = [
  { id: 'learn', number: '01', label: '认识量子', tooltip: '从量子比特和量子门开始，理解量子计算基础概念' },
  { id: 'experiments', number: '02', label: '探索实验', tooltip: '通过经典量子实验，观察量子程序如何运行' },
  { id: 'explorer', number: '03', label: '自由探索', tooltip: '自由探索量子程序，使用 AI 创建和验证实验' },
  { id: 'repair', number: '04', label: '程序修复', tooltip: '分析并修复已有量子程序的问题' },
  { id: 'backend', number: '05', label: '执行平台', tooltip: '查看量子程序支持的执行平台和运行环境' },
]

export function GlobalNavigation({ current, onNavigate }: GlobalNavigationProps) {
  return (
    <header className="global-header">
      <button className="global-brand" onClick={() => onNavigate('learn')} aria-label="返回 LoomQ 首页">
        <span className="brand-mark"><i>L</i></span>
        <strong>LoomQ</strong>
      </button>
      <nav className="global-nav" aria-label="LoomQ 全局能力导航">
        {NAV_ITEMS.map((item) => (
          <button
            className={current === item.id ? 'active' : ''}
            aria-current={current === item.id ? 'page' : undefined}
            aria-label={`${item.label}：${item.tooltip}`}
            key={item.id}
            onClick={() => onNavigate(item.id)}
            title={item.tooltip}
          >
            <span>{item.number}</span>
            <strong>{item.label}</strong>
          </button>
        ))}
      </nav>
    </header>
  )
}

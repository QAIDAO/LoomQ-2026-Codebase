type RecoveryGuidanceProps = {
  title: string
  whatHappened: string
  possibleReason: string
  nextStep: string
  onRetry: () => void
  onModify: () => void
  retryLabel: string
  modifyLabel: string
}

/**
 * 请求失败时复用同一份新手恢复指引；只展示安全的用户操作信息。
 */
export function RecoveryGuidance({
  title,
  whatHappened,
  possibleReason,
  nextStep,
  onRetry,
  onModify,
  retryLabel,
  modifyLabel,
}: RecoveryGuidanceProps) {
  return (
    <section className="recovery-guidance" role="alert" aria-label={`${title}：恢复指引`}>
      <header>
        <span aria-hidden="true">!</span>
        <div><small>需要再试一次</small><h2>{title}</h2></div>
      </header>
      <dl>
        <div><dt>发生了什么</dt><dd>{whatHappened}</dd></div>
        <div><dt>可能原因</dt><dd>{possibleReason}</dd></div>
        <div><dt>下一步操作</dt><dd>{nextStep}</dd></div>
      </dl>
      <div className="recovery-actions">
        <button type="button" onClick={onRetry}>{retryLabel}</button>
        <button type="button" onClick={onModify}>{modifyLabel}</button>
      </div>
    </section>
  )
}

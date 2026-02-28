import type { Config } from 'tailwindcss'

// Tailwind CSS v3 설정: CSS 변수 기반 다크 테마
const config: Config = {
  // 클래스 기반 다크 모드 (html에 class="dark" 부여)
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // 배경 계층
        'bg-primary':   'var(--bg-primary)',
        'bg-secondary': 'var(--bg-secondary)',
        'bg-tertiary':  'var(--bg-tertiary)',
        'bg-elevated':  'var(--bg-elevated)',
        // 텍스트
        'text-primary':   'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
        'text-muted':     'var(--text-muted)',
        // 발전소 상태
        'status-active':    'var(--status-active)',
        'status-stopped':   'var(--status-stopped)',
        'status-retired':   'var(--status-retired)',
        'status-no-coord':  'var(--status-no-coord)',
        // 인프라
        'infra-substation': 'var(--infra-substation)',
        'infra-powerline':  'var(--infra-powerline)',
        // 액센트
        'accent-primary': 'var(--accent-primary)',
        'accent-hover':   'var(--accent-hover)',
        // 경계선
        'border-default': 'var(--border-default)',
        'border-hover':   'var(--border-hover)',
      },
      // 패널 너비 고정
      width: {
        'side-panel': '420px',
      },
    },
  },
  plugins: [],
}

export default config

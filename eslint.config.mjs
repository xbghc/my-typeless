// ESLint flat config（ESLint 9 + typescript-eslint 8）。
// 目标：务实可过——typescript-eslint recommended + react-hooks，未用变量降为 warn 且放行 `_` 前缀。
import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'

export default tseslint.config(
  { ignores: ['out/**', 'release/**', 'dist/**', 'node_modules/**', 'resources/**'] },

  js.configs.recommended,
  ...tseslint.configs.recommended,

  {
    files: ['**/*.{ts,tsx}'],
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrors: 'none' },
      ],
    },
  },

  // renderer（React）与 audio worker：浏览器全局。
  {
    files: ['src/renderer/**/*.{ts,tsx}', 'src/audio/**/*.ts'],
    languageOptions: { globals: { ...globals.browser } },
  },

  // main / preload / 构建脚本：Node 全局。
  {
    files: [
      'src/main/**/*.ts',
      'src/preload/**/*.ts',
      'scripts/**/*.mjs',
      'electron.vite.config.ts',
      'tests/**/*.ts',
    ],
    languageOptions: { globals: { ...globals.node } },
  },

  // AudioWorklet 纯 JS：worklet 作用域的全局不在 globals.browser 中，单列。
  {
    files: ['**/*.worklet.js'],
    languageOptions: {
      globals: {
        sampleRate: 'readonly',
        currentFrame: 'readonly',
        currentTime: 'readonly',
        AudioWorkletProcessor: 'readonly',
        registerProcessor: 'readonly',
      },
    },
  },

  // 根目录构建配置（postcss / tailwind）是 CommonJS，单列以放行 module/require。
  {
    files: ['**/*.config.{js,cjs}'],
    languageOptions: { sourceType: 'commonjs', globals: { ...globals.node } },
    rules: { '@typescript-eslint/no-require-imports': 'off' },
  },
)

// Provider 规范化与 active 解析，移植自旧版 app.js 的同名工具函数。
import type { ProviderConfig, ProviderType } from '@shared/types'

interface RawProvider {
  id?: string
  name?: string
  base_url?: string
  api_key?: string
  models?: unknown
  provider_type?: string
}

export function normalizeProviders(providers: unknown): ProviderConfig[] {
  if (!Array.isArray(providers)) return []
  return (providers as RawProvider[]).map((p, index) => ({
    id: p.id || `provider-${index + 1}`,
    name: p.name || p.id || `Provider ${index + 1}`,
    base_url: p.base_url || '',
    api_key: p.api_key || '',
    models: Array.isArray(p.models) ? (p.models as unknown[]).filter(Boolean).map(String) : [],
    provider_type: (p.provider_type as ProviderType) || 'openai',
  }))
}

export function findProvider(providers: ProviderConfig[], id: string): ProviderConfig | null {
  return providers.find((p) => p.id === id) || providers[0] || null
}

export function resolveActiveProviderId(providers: ProviderConfig[], configuredId?: string): string {
  if (!providers.length) return ''
  if (configuredId && providers.some((p) => p.id === configuredId)) return configuredId
  return providers[0].id
}

export function resolveActiveModel(
  providers: ProviderConfig[],
  providerId: string,
  configuredModel?: string,
): string {
  const provider = findProvider(providers, providerId)
  if (!provider || !provider.models.length) return ''
  if (configuredModel && provider.models.includes(configuredModel)) return configuredModel
  return provider.models[0]
}

export function generateId(): string {
  const uuid = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : ''
  if (uuid) return uuid.replace(/-/g, '').slice(0, 12)
  return Math.random().toString(36).slice(2, 14)
}

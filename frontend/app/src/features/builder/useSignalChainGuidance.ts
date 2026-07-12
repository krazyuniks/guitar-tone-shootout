import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../../api/client.ts'
import {
  DEFAULT_GUIDANCE,
  guidanceAffordances,
  projectGuidanceBlocks,
  type ChainDraft,
  type GuidanceResponse,
} from './model.ts'

export function useSignalChainGuidance(draft: ChainDraft) {
  const blocks = projectGuidanceBlocks(draft)
  const signature = blocks.map((block) => block.gear_type).join(',')
  const query = useQuery({
    queryKey: ['signal-chain-guidance', signature],
    queryFn: async (): Promise<GuidanceResponse> => {
      const { data } = await apiClient.POST('/api/signal-chains/guidance', {
        body: { blocks },
      })
      if (!data) throw new Error('Guidance response was empty')
      return data
    },
    enabled: blocks.length > 0,
    staleTime: 1_000,
    placeholderData: (previousData) => previousData,
  })
  const guidance = blocks.length === 0 ? DEFAULT_GUIDANCE : (query.data ?? DEFAULT_GUIDANCE)

  return {
    guidance,
    ...guidanceAffordances(guidance),
    isLoading: blocks.length > 0 && query.isLoading,
    error: query.error,
  }
}

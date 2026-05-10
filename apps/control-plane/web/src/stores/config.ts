import { defineStore } from 'pinia';
import { ref } from 'vue';
import { api } from '../api/client';

export const useConfigStore = defineStore('config', () => {
  const config = ref<Record<string, any> | null>(null);
  const draft = ref<Record<string, any> | null>(null);
  const lastError = ref<string | null>(null);
  const currentClusterId = ref<string>('default');

  async function fetchConfig() {
    lastError.value = null;
    try {
      const payload = await api.getConfig();
      config.value = payload.config;
      draft.value = JSON.parse(JSON.stringify(payload.config));
      const clusters = (payload.config.clusters as Array<{ id: string }>) || [];
      if (clusters.length > 0 && !clusters.find((c) => c.id === currentClusterId.value)) {
        currentClusterId.value = clusters[0].id;
      }
    } catch (err) {
      lastError.value = (err as Error).message;
    }
  }

  async function applyDraft() {
    lastError.value = null;
    if (!draft.value) return false;
    try {
      const payload = (await api.putConfig(draft.value)) as {
        ok: boolean;
        config: Record<string, any>;
      };
      if (payload.ok) {
        config.value = payload.config;
        draft.value = JSON.parse(JSON.stringify(payload.config));
      }
      return payload.ok;
    } catch (err) {
      lastError.value = (err as Error).message;
      return false;
    }
  }

  return { config, draft, lastError, currentClusterId, fetchConfig, applyDraft };
});

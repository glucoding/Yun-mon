<template>
  <div>
    <header class="actions">
      <button class="btn" @click="load">刷新</button>
      <button class="btn btn-ghost" @click="syncMetadata">从 Prometheus 同步元数据</button>
    </header>

    <section v-for="cat in categories" :key="cat.id" class="catalog-section">
      <h3>{{ cat.name }}</h3>
      <p class="muted">{{ cat.description }}</p>
      <table class="data-table">
        <thead>
          <tr>
            <th>显示名</th>
            <th>指标名</th>
            <th>来源</th>
            <th>规则模式</th>
            <th>是否在线</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in itemsByCategory[cat.id] ?? []" :key="m.metricId">
            <td>{{ m.displayName }}</td>
            <td><code>{{ m.metricName }}</code></td>
            <td>{{ m.sourceType }}</td>
            <td>{{ m.ruleMode }}</td>
            <td>{{ m.live ? '是' : '否' }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="unmanaged.length > 0" class="catalog-section">
      <h3>未纳管 Live 指标</h3>
      <p class="muted">以下指标已被 Prometheus 实时抓到,但还没有对应的目录条目。</p>
      <ul>
        <li v-for="m in unmanaged" :key="m.metricName"><code>{{ m.metricName }}</code> · 推荐分类: {{ m.recommendedCategoryName }}</li>
      </ul>
    </section>

    <p v-if="syncMessage" class="message">{{ syncMessage }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { api } from '../api/client';

interface CatalogCategory {
  id: string;
  name: string;
  description?: string;
}

interface CatalogItem {
  metricId: string;
  metricName: string;
  displayName: string;
  category: string;
  sourceType: string;
  ruleMode: string;
  live?: boolean;
}

interface UnmanagedItem {
  metricName: string;
  recommendedCategoryName?: string;
}

const categories = ref<CatalogCategory[]>([]);
const items = ref<CatalogItem[]>([]);
const unmanaged = ref<UnmanagedItem[]>([]);
const syncMessage = ref('');

const itemsByCategory = computed<Record<string, CatalogItem[]>>(() => {
  const map: Record<string, CatalogItem[]> = {};
  for (const it of items.value) {
    (map[it.category] ||= []).push(it);
  }
  return map;
});

async function load() {
  const payload = (await api.metricCatalog()) as {
    categories: CatalogCategory[];
    items: CatalogItem[];
    unmanagedLiveMetrics: UnmanagedItem[];
  };
  categories.value = payload.categories ?? [];
  items.value = payload.items ?? [];
  unmanaged.value = payload.unmanagedLiveMetrics ?? [];
}

async function syncMetadata() {
  syncMessage.value = '正在同步…';
  try {
    const payload = (await api.syncMetricCatalog()) as { ok: boolean; metadata?: unknown; error?: string };
    syncMessage.value = payload.ok ? '同步成功,已拿到 Prometheus metadata' : `同步失败: ${payload.error}`;
  } catch (err) {
    syncMessage.value = `同步失败: ${(err as Error).message}`;
  }
}

onMounted(load);
</script>

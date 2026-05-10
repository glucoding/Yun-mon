<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="logo">YM</div>
        <div>
          <div class="brand-name">Yun-mon</div>
          <div class="brand-subtitle">监测控制台</div>
        </div>
      </div>
      <nav class="nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          active-class="nav-item--active"
        >
          <span class="nav-bullet" />
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="cluster-switch" v-if="state.clusters.length > 0">
        <label>当前集群</label>
        <select v-model="currentClusterId">
          <option v-for="c in state.clusters" :key="c.id" :value="c.id">
            {{ c.name }}
          </option>
        </select>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="topbar-left">
          <h1>{{ activeTitle }}</h1>
          <p v-if="activeSubtitle" class="topbar-subtitle">{{ activeSubtitle }}</p>
        </div>
        <div class="topbar-right">
          <button class="btn btn-ghost" :disabled="loading" @click="reload">
            {{ loading ? '正在刷新…' : '刷新' }}
          </button>
        </div>
      </header>

      <section class="content">
        <RouterView v-if="!loading && state.system" />
        <div v-else class="placeholder">正在加载控制面状态…</div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';
import { useConfigStore } from './stores/config';

const navItems = [
  { path: '/', label: '运行总览' },
  { path: '/config', label: '平台配置' },
  { path: '/applications', label: '应用纳管' },
  { path: '/metrics', label: '指标目录' },
  { path: '/audit', label: '审计与回滚' },
  { path: '/jobs', label: '任务流水' },
];

const route = useRoute();
const store = useConfigStore();
const loading = ref(true);

const state = computed(() => store.config ?? { clusters: [] });
const currentClusterId = computed({
  get: () => store.currentClusterId,
  set: (value: string) => (store.currentClusterId = value),
});

const activeTitle = computed(() => navItems.find((n) => n.path === route.path)?.label ?? 'Yun-mon');
const activeSubtitle = computed(() => {
  if (route.path === '/audit') return '配置版本/diff/回滚';
  if (route.path === '/jobs') return '后台任务进度与日志';
  if (route.path === '/applications') return '基于 Docker 标签的纳管和发现';
  if (route.path === '/metrics') return '指标目录、规则、Live 指标';
  return '';
});

async function reload() {
  loading.value = true;
  try {
    await store.fetchConfig();
  } finally {
    loading.value = false;
  }
}

onMounted(reload);
</script>

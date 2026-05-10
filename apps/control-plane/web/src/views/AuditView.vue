<template>
  <div>
    <p class="muted">每次保存配置都会落一份快照,包含 RFC6902 JSON Patch 与完整 state。</p>
    <table class="data-table">
      <thead>
        <tr>
          <th>快照 ID</th>
          <th>时间</th>
          <th>操作者</th>
          <th>摘要</th>
          <th>diff 数</th>
          <th>动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="snap in snapshots" :key="snap.snapshotId">
          <td><code>{{ snap.snapshotId }}</code></td>
          <td>{{ snap.appliedAt }}</td>
          <td>{{ snap.actor }}</td>
          <td>{{ snap.summary }}</td>
          <td>{{ snap.diffOpsCount }}</td>
          <td>
            <button class="btn btn-ghost" @click="rollback(snap.snapshotId)">回滚到此版本</button>
            <button class="btn btn-ghost" @click="showDetail(snap.snapshotId)">查看 diff</button>
          </td>
        </tr>
      </tbody>
    </table>

    <pre v-if="detail" class="json-detail">{{ JSON.stringify(detail, null, 2) }}</pre>
    <p v-if="message" class="message">{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from '../api/client';

interface SnapshotMeta {
  snapshotId: string;
  appliedAt: string;
  actor: string;
  summary: string;
  diffOpsCount: number;
}

const snapshots = ref<SnapshotMeta[]>([]);
const detail = ref<Record<string, unknown> | null>(null);
const message = ref('');

async function load() {
  const payload = await api.listSnapshots();
  snapshots.value = (payload.snapshots ?? []) as unknown as SnapshotMeta[];
}

async function showDetail(id: string) {
  const payload = await api.getSnapshot(id);
  detail.value = payload.snapshot;
}

async function rollback(id: string) {
  if (!confirm(`确认回滚到 ${id} ?这会重新渲染所有组件配置并热重载 Prometheus。`)) return;
  message.value = '回滚中…';
  try {
    await api.rollback(id);
    message.value = '回滚成功';
    await load();
  } catch (err) {
    message.value = `回滚失败: ${(err as Error).message}`;
  }
}

onMounted(load);
</script>

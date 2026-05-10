<template>
  <div>
    <button class="btn" @click="load">刷新</button>
    <table class="data-table">
      <thead>
        <tr>
          <th>Job ID</th>
          <th>名称</th>
          <th>状态</th>
          <th>进度</th>
          <th>开始时间</th>
          <th>完成时间</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="job in jobs" :key="job.id">
          <td><code>{{ job.id }}</code></td>
          <td>{{ job.name }}</td>
          <td>{{ job.status }}</td>
          <td>{{ job.progress }}%</td>
          <td>{{ job.startedAt ?? '-' }}</td>
          <td>{{ job.finishedAt ?? '-' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from '../api/client';

interface Job {
  id: string;
  name: string;
  status: string;
  progress: number;
  startedAt?: string;
  finishedAt?: string;
}

const jobs = ref<Job[]>([]);

async function load() {
  const payload = await api.listJobs();
  jobs.value = (payload.jobs ?? []) as unknown as Job[];
}

onMounted(load);
</script>

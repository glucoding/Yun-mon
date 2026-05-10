import { createRouter, createWebHashHistory } from 'vue-router';

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: () => import('./views/OverviewView.vue') },
    { path: '/config', component: () => import('./views/ConfigView.vue') },
    { path: '/applications', component: () => import('./views/ApplicationsView.vue') },
    { path: '/metrics', component: () => import('./views/MetricCatalogView.vue') },
    { path: '/audit', component: () => import('./views/AuditView.vue') },
    { path: '/jobs', component: () => import('./views/JobsView.vue') },
  ],
});

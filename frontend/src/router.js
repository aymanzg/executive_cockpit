import { createRouter, createWebHistory } from 'vue-router'

export const routes = [
  { path: '/', redirect: '/overview' },
  {
    path: '/overview', name: 'overview', component: () => import('./views/Overview.vue'),
    meta: { title: 'النظرة العامة', short: 'النظرة', sub: 'أهم المؤشرات للفترة المختارة', icon: 'overview' },
  },
  {
    path: '/sales', name: 'sales', component: () => import('./views/Sales.vue'),
    meta: { title: 'دورة المبيعات', short: 'المبيعات', sub: 'من عرض السعر إلى أمر البيع ثم الفاتورة والتحصيل', icon: 'sales' },
  },
  {
    path: '/reps', name: 'reps', component: () => import('./views/Reps.vue'),
    meta: { title: 'أداء المندوبين', short: 'المندوبون', sub: 'المبيعات الشهرية لكل مندوب خلال السنة', icon: 'reps', ownPeriod: true },
  },
  {
    path: '/collection', name: 'collection', component: () => import('./views/Collection.vue'),
    meta: { title: 'التحصيل والذمم المدينة', short: 'التحصيل', sub: 'صافي الذمم، أعمارها، وأكبر المدينين', icon: 'collection' },
  },
  {
    path: '/profit', name: 'profit', component: () => import('./views/Profit.vue'),
    meta: { title: 'الربحية', short: 'الربحية', sub: 'محسوبة من القيود المحاسبية وليس من تقييم المخزون', icon: 'profit' },
  },
  {
    path: '/vat', name: 'vat', component: () => import('./views/Vat.vue'),
    meta: { title: 'ضريبة القيمة المضافة', short: 'الضريبة', sub: 'الإقرار وسجلا المبيعات والمشتريات، مطابقة لميزان المراجعة بالهللة', icon: 'vat', ownPeriod: true },
  },
  {
    path: '/hr', name: 'hr', component: () => import('./views/HR.vue'),
    meta: { title: 'الموارد البشرية', short: 'الموظفون', sub: 'الرواتب، الإجازات، السلف، والعُهد', icon: 'hr' },
  },
  { path: '/:pathMatch(.*)*', redirect: '/overview' },
]

const router = createRouter({ history: createWebHistory('/executive'), routes })

router.afterEach((to) => {
  document.title = `${to.meta.title || 'لوحة القيادة'} · لوحة القيادة التنفيذية`
})

export default router

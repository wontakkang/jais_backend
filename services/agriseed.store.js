// 사용방법:
// 1. 컴포넌트에서 import 합니다: import { useAgriseedStore } from '@/services/agriseed.store.js'
// 2. setup() 함수 내에서 스토어를 초기화합니다: const agriseedStore = useAgriseedStore();
// 3. 필요한 액션을 호출합니다: agriseedStore.fetchDevices({ page:1, ordering: '-id' });
// 4. state 데이터는 agriseedStore.devices 등에서 참조할 수 있습니다.

import { defineStore } from 'pinia';
import { AgriseedService } from './agriseed.service';
import { showToast } from './domUtils';

// Common params: filtering and ordering via `params`, e.g. { status: 'active', ordering: '-id' }
export const useAgriseedStore = defineStore('agriseed', {
  state: () => ({
    devices: [],
    activities: [],
    recipeProfiles: [],
    comments: [],
    performances: [],
    ratings: []
  }),
  actions: {
    // Devices CRUD
    async fetchDevices(params) {
      this.devices = await AgriseedService.listDevices(params);
    },
    async getDevice(id) {
      return await AgriseedService.detailDevice(id);
    },
    async createDevice(data) {
      const d = await AgriseedService.createDevice(data);
      this.devices.push(d);
      return d;
    },
    async updateDevice(id, data) {
      const updated = await AgriseedService.updateDevice(id, data);
      const idx = this.devices.findIndex(x => x.id === id);
      if (idx !== -1) this.devices.splice(idx, 1, updated);
      return updated;
    },
    async deleteDevice(id) {
      await AgriseedService.removeDevice(id);
      this.devices = this.devices.filter(x => x.id !== id);
    },
    // Activities CRUD
    async fetchActivities(params) {
      this.activities = await AgriseedService.listActivities(params);
    },
    async createActivity(data) {
      const a = await AgriseedService.createActivity(data);
      this.activities.push(a);
      return a;
    },
    async updateActivity(id, data) {
      const updated = await AgriseedService.updateActivity(id, data);
      const idx = this.activities.findIndex(x => x.id === id);
      if (idx !== -1) this.activities.splice(idx, 1, updated);
      return updated;
    },
    async deleteActivity(id) {
      await AgriseedService.removeActivity(id);
      this.activities = this.activities.filter(x => x.id !== id);
    },
    // RecipeProfiles CRUD
    async fetchRecipes(params) {
      this.recipeProfiles = await AgriseedService.listRecipes(params);
    },
    async fetchRecipesByVariety(varietyId, params) {
      this.recipeProfiles = await AgriseedService.listRecipesByVariety(varietyId, params);
    },
    async createRecipe(data) {
      const r = await AgriseedService.createRecipe(data);
      this.recipeProfiles.push(r);
      return r;
    },
    async updateRecipe(id, data) {
      const updated = await AgriseedService.updateRecipe(id, data);
      const idx = this.recipeProfiles.findIndex(x => x.id === id);
      if (idx !== -1) this.recipeProfiles.splice(idx, 1, updated);
      return updated;
    },
    async deleteRecipe(id) {
      await AgriseedService.removeRecipe(id);
      this.recipeProfiles = this.recipeProfiles.filter(x => x.id !== id);
    },
    // Comments
    async fetchComments(params) {
      this.comments = await AgriseedService.listComments(params);
    },
    async createComment(data) {
      const c = await AgriseedService.createComment(data);
      this.comments.push(c);
      return c;
    },
    // Performances
    async fetchPerformances(params) {
      this.performances = await AgriseedService.listPerformances(params);
    },
    async createPerformance(data) {
      const p = await AgriseedService.createPerformance(data);
      this.performances.push(p);
      return p;
    },
    // Ratings
    async fetchRatings(params) {
      this.ratings = await AgriseedService.listRatings(params);
    },
    async createRating(data) {
      const r = await AgriseedService.createRating(data);
      this.ratings.push(r);
      return r;
    }
  }
});
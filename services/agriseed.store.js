// 사용방법:
// 1. 컴포넌트에서 import 합니다: import { useAgriseedStore } from '@/services/agriseed.store.js'
// 2. setup() 함수 내에서 스토어를 초기화합니다: const agriseedStore = useAgriseedStore();
// 3. 필요한 액션을 호출합니다: agriseedStore.fetchDevices({ page:1, ordering: '-id' });
// 4. state 데이터는 agriseedStore.devices 등에서 참조할 수 있습니다.

import { defineStore } from 'pinia';
import { AgriseedService } from './agriseed.service';
import { normalizeList } from '@/utils/normalize';

// Common params: filtering and ordering via `params`, e.g. { status: 'active', ordering: '-id' }
export const useAgriseedStore = defineStore('agriseed', {
  state: () => ({
    devices: [],
    activities: [],
    facilities: [],
    zones: [],
    controlSettings: [],
    recipeProfiles: [],
    comments: [],
    performances: [],
    ratings: [],
    varieties: [],
    crops: [],
    // 개별 레시피 항목값(RecipeItemValues) 캐시
    recipeItemValues: [],
    // 추가된 엔드포인트 캐시
    controlHistories: [],
    controlRoles: [],
    issues: [],
    resolvedIssues: [],
    schedules: [],
    sensorData: [],
    facilityHistories: [],
    varietyImages: [],
    varietyGuides: [],
    controlItems: [],
    commentVotes: [],
    // Tree images 및 Specimens 관련 캐시 추가
    treeImages: [],
    specimens: [],
    // Trees 및 태그 캐시
    trees: [],
    treeTags: [],
    // 전역 로딩/에러 상태
    isLoading: false,
    lastError: null
  }),
  actions: {
    // 공통 헬퍼: 컬렉션을 다루는 기본 CRUD 로직을 중복 없이 처리
    async _fetchCollection(stateKey, listMethod, params) {
      this.isLoading = true; this.lastError = null;
      try {
        const res = await listMethod(params);
        // 서비스 응답을 중앙 normalizeList 유틸로 정규화
        const list = normalizeList(res)
        this[stateKey] = list
        return list
      } catch (error) {
        this.lastError = error;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    async _getItem(getMethod, id) {
      this.isLoading = true; this.lastError = null;
      try {
        return await getMethod(id)
      } catch (error) {
        this.lastError = error; throw error
      } finally { this.isLoading = false }
    },
    async _createItem(stateKey, createMethod, data) {
      this.isLoading = true; this.lastError = null;
      try {
        const item = await createMethod(data)
        if (stateKey && Array.isArray(this[stateKey])) this[stateKey].push(item)
        return item
      } catch (error) {
        this.lastError = error; throw error
      } finally { this.isLoading = false }
    },
    async _updateItem(stateKey, updateMethod, id, data) {
      this.isLoading = true; this.lastError = null;
      try {
        const updated = await updateMethod(id, data)
        if (stateKey && Array.isArray(this[stateKey])) {
          const idx = this[stateKey].findIndex(x => x.id === id)
          if (idx !== -1) this[stateKey].splice(idx, 1, updated)
        }
        return updated
      } catch (error) {
        this.lastError = error; throw error
      } finally { this.isLoading = false }
    },
    async _deleteItem(stateKey, deleteMethod, id) {
      this.isLoading = true; this.lastError = null;
      try {
        await deleteMethod(id)
        if (stateKey && Array.isArray(this[stateKey])) this[stateKey] = this[stateKey].filter(x => x.id !== id)
      } catch (error) {
        this.lastError = error; throw error
      } finally { this.isLoading = false }
    },

    // Devices CRUD
    async fetchDevices(params) { return await this._fetchCollection('devices', AgriseedService.listDevices, params) },
    async getDevice(id) { return await this._getItem(AgriseedService.detailDevice, id) },
    async createDevice(data) { return await this._createItem('devices', AgriseedService.createDevice, data) },
    async updateDevice(id, data) { return await this._updateItem('devices', AgriseedService.updateDevice, id, data) },
    async deleteDevice(id) { return await this._deleteItem('devices', AgriseedService.removeDevice, id) },

    // Facilities CRUD
    async fetchFacilities(params) { return await this._fetchCollection('facilities', AgriseedService.listFacilities, params) },
    async getFacility(id) { return await this._getItem(AgriseedService.detailFacility, id) },
    async createFacility(data) { return await this._createItem('facilities', AgriseedService.createFacility, data) },
    async updateFacility(id, data) { return await this._updateItem('facilities', AgriseedService.updateFacility, id, data) },
    async patchFacility(id, data) { return await this._updateItem('facilities', AgriseedService.patchFacility, id, data) },
    async deleteFacility(id) { return await this._deleteItem('facilities', AgriseedService.removeFacility, id) },

    // Varieties CRUD
    async fetchVarieties(params) { return await this._fetchCollection('varieties', AgriseedService.listVarieties, params) },
    async getVariety(id) { return await this._getItem(AgriseedService.detailVariety, id) },
    async createVariety(data) { return await this._createItem('varieties', AgriseedService.createVariety, data) },
    async updateVariety(id, data) { return await this._updateItem('varieties', AgriseedService.updateVariety, id, data) },
    async patchVariety(id, data) { return await this._updateItem('varieties', AgriseedService.patchVariety, id, data) },
    async deleteVariety(id) { return await this._deleteItem('varieties', AgriseedService.removeVariety, id) },

    // Crops CRUD
    async fetchCrops(params) { return await this._fetchCollection('crops', AgriseedService.listCrops, params) },
    async getCrop(id) { return await this._getItem(AgriseedService.detailCrop, id) },
    async createCrop(data) { return await this._createItem('crops', AgriseedService.createCrop, data) },
    async updateCrop(id, data) { return await this._updateItem('crops', AgriseedService.updateCrop, id, data) },
    async patchCrop(id, data) { return await this._updateItem('crops', AgriseedService.patchCrop, id, data) },
    async deleteCrop(id) { return await this._deleteItem('crops', AgriseedService.removeCrop, id) },

    // Zones CRUD
    async fetchZones(params) { return await this._fetchCollection('zones', AgriseedService.listZones, params) },
    async getZone(id) { return await this._getItem(AgriseedService.detailZone, id) },
    async createZone(data) { return await this._createItem('zones', AgriseedService.createZone, data) },
    async updateZone(id, data) { return await this._updateItem('zones', AgriseedService.updateZone, id, data) },
    async deleteZone(id) { return await this._deleteItem('zones', AgriseedService.removeZone, id) },

    // ControlSettings CRUD
    async fetchControlSettings(params) { return await this._fetchCollection('controlSettings', AgriseedService.listControlSettings, params) },
    async getControlSetting(id) { return await this._getItem(AgriseedService.detailControlSetting, id) },
    async createControlSetting(data) { return await this._createItem('controlSettings', AgriseedService.createControlSetting, data) },
    async updateControlSetting(id, data) { return await this._updateItem('controlSettings', AgriseedService.updateControlSetting, id, data) },
    async deleteControlSetting(id) { return await this._deleteItem('controlSettings', AgriseedService.removeControlSetting, id) },

    // Activities CRUD
    async fetchActivities(params) { return await this._fetchCollection('activities', AgriseedService.listActivities, params) },
    async createActivity(data) { return await this._createItem('activities', AgriseedService.createActivity, data) },
    async updateActivity(id, data) { return await this._updateItem('activities', AgriseedService.updateActivity, id, data) },
    async deleteActivity(id) { return await this._deleteItem('activities', AgriseedService.removeActivity, id) },

    // Control histories
    async fetchControlHistories(params) { return await this._fetchCollection('controlHistories', AgriseedService.listControlHistories, params) },
    async getControlHistory(id) { return await this._getItem(AgriseedService.detailControlHistory, id) },

    // Control roles
    async fetchControlRoles(params) { return await this._fetchCollection('controlRoles', AgriseedService.listControlRoles, params) },
    async getControlRole(id) { return await this._getItem(AgriseedService.detailControlRole, id) },

    // Issues
    async fetchIssues(params) { return await this._fetchCollection('issues', AgriseedService.listIssues, params) },
    async getIssue(id) { return await this._getItem(AgriseedService.detailIssue, id) },
    async createIssue(data) { return await this._createItem('issues', AgriseedService.createIssue, data) },
    async updateIssue(id, data) { return await this._updateItem('issues', AgriseedService.updateIssue, id, data) },
    async deleteIssue(id) { return await this._deleteItem('issues', AgriseedService.removeIssue, id) },

    // Resolved issues
    async fetchResolvedIssues(params) { return await this._fetchCollection('resolvedIssues', AgriseedService.listResolvedIssues, params) },

    // Schedules
    async fetchSchedules(params) { return await this._fetchCollection('schedules', AgriseedService.listSchedules, params) },
    async getSchedule(id) { return await this._getItem(AgriseedService.detailSchedule, id) },
    async createSchedule(data) { return await this._createItem('schedules', AgriseedService.createSchedule, data) },
    async updateSchedule(id, data) { return await this._updateItem('schedules', AgriseedService.updateSchedule, id, data) },
    async deleteSchedule(id) { return await this._deleteItem('schedules', AgriseedService.removeSchedule, id) },

    // Sensor data
    async fetchSensorData(params) { return await this._fetchCollection('sensorData', AgriseedService.listSensorData, params) },

    // Facility histories
    async fetchFacilityHistories(params) { return await this._fetchCollection('facilityHistories', AgriseedService.listFacilityHistories, params) },

    // Variety images
    async fetchVarietyImages(params) { return await this._fetchCollection('varietyImages', AgriseedService.listVarietyImages, params) },
    async uploadVarietyImage(data) { return await this._createItem('varietyImages', AgriseedService.createVarietyImage, data) },
    async deleteVarietyImage(id) { return await this._deleteItem('varietyImages', AgriseedService.removeVarietyImage, id) },

    // Variety guides
    async fetchVarietyGuides(params) { return await this._fetchCollection('varietyGuides', AgriseedService.listVarietyGuides, params) },
    async createVarietyGuide(data) { return await this._createItem('varietyGuides', AgriseedService.createVarietyGuide, data) },
    async deleteVarietyGuide(id) { return await this._deleteItem('varietyGuides', AgriseedService.removeVarietyGuide, id) },

    // Tree images
    async fetchTreeImages(params) { return await this._fetchCollection('treeImages', AgriseedService.listTreeImages, params) },
    async uploadTreeImage(data) { return await this._createItem('treeImages', AgriseedService.uploadTreeImage, data) },
    async deleteTreeImage(id) { return await this._deleteItem('treeImages', AgriseedService.removeTreeImage, id) },

    // Trees CRUD
    async fetchTrees(params) { return await this._fetchCollection('trees', AgriseedService.listTrees, params) },
    async getTree(id) { return await this._getItem(AgriseedService.detailTree, id) },
    async createTree(data) { return await this._createItem('trees', AgriseedService.createTree, data) },
    async updateTree(id, data) { return await this._updateItem('trees', AgriseedService.updateTree, id, data) },
    async patchTree(id, data) { return await this._updateItem('trees', AgriseedService.patchTree, id, data) },
    async deleteTree(id) { return await this._deleteItem('trees', AgriseedService.removeTree, id) },

    // Tree tags CRUD
    async fetchTreeTags(params) { return await this._fetchCollection('treeTags', AgriseedService.listTreeTags, params) },
    async createTreeTag(data) { return await this._createItem('treeTags', AgriseedService.createTreeTag, data) },
    async deleteTreeTag(id) { return await this._deleteItem('treeTags', AgriseedService.removeTreeTag, id) },

    // Specimens (표본)
    async fetchSpecimens(params) { return await this._fetchCollection('specimens', AgriseedService.listSpecimens, params) },
    async getSpecimen(id) { return await this._getItem(AgriseedService.detailSpecimen, id) },
    async createSpecimen(data) { return await this._createItem('specimens', AgriseedService.createSpecimen, data) },
    async updateSpecimen(id, data) { return await this._updateItem('specimens', AgriseedService.updateSpecimen, id, data) },
    async patchSpecimen(id, data) { return await this._updateItem('specimens', AgriseedService.patchSpecimen, id, data) },
    async deleteSpecimen(id) { return await this._deleteItem('specimens', AgriseedService.removeSpecimen, id) },

    // Specimen attachments 업로드 (성공 시 로컬 상태에 반영)
    async uploadSpecimenAttachments(specimenId, files) {
      const res = await AgriseedService.uploadSpecimenAttachments(specimenId, files)
      // 응답에 created 배열이 있으면 specimens 캐시에 반영
      try {
        if (res && res.created && Array.isArray(res.created)) {
          const idx = this.specimens.findIndex(s => s.id === specimenId)
          if (idx !== -1) {
            const specimen = { ...this.specimens[idx] }
            specimen.attachments_files = (specimen.attachments_files || []).concat(res.created)
            this.specimens.splice(idx, 1, specimen)
          }
        }
      } catch (e) {
        // 상태 반영 실패는 무시하되 에러로 기록
        this.lastError = e
      }
      return res
    },

    // Control items (정적 목록으로 사용될 수 있음)
    async fetchControlItems(params) { return await this._fetchCollection('controlItems', AgriseedService.listControlItems, params) },

    // Comment votes
    async fetchCommentVotes(params) { return await this._fetchCollection('commentVotes', AgriseedService.listVotes, params) },
    async createCommentVote(data) { return await this._createItem('commentVotes', AgriseedService.createVote, data) },
    async deleteCommentVote(id) { return await this._deleteItem('commentVotes', AgriseedService.removeVote, id) },

    // RecipeProfiles (특별 처리 유지)
    async fetchRecipes(params) {
      const res = await AgriseedService.listRecipes(params)
      const list = normalizeList(res)
      this.recipeProfiles = list
      return list
    },
    async fetchRecipesByVariety(varietyId, params) { return await this._fetchCollection('recipeProfiles', (p) => AgriseedService.listRecipesByVariety(varietyId, p), params) },
    async createRecipe(data) { return await this._createItem('recipeProfiles', AgriseedService.createRecipe, data) },
    async updateRecipe(id, data) { return await this._updateItem('recipeProfiles', AgriseedService.updateRecipe, id, data) },
    async patchRecipe(id, data) { return await this._updateItem('recipeProfiles', AgriseedService.patchRecipe, id, data) },
    async deleteRecipe(id) { return await this._deleteItem('recipeProfiles', AgriseedService.removeRecipe, id) },

    // recipe-step 단위의 create/patch 노출
    async createRecipeStep(data) { return await AgriseedService.createRecipeStep(data) },
    async patchRecipeStep(id, data) { return await AgriseedService.patchRecipeStep(id, data) },
    async detailRecipeStep(id) { return await AgriseedService.detailRecipeStep(id) },
    async removeRecipeStep(id) { return await AgriseedService.removeRecipeStep(id) },

    // Recipe item values CRUD 캐시 사용
    async fetchRecipeItemValues(params) { this.recipeItemValues = normalizeList(await AgriseedService.listRecipeItemValues(params)); return this.recipeItemValues },
    async detailRecipeItemValue(id) { return await AgriseedService.detailRecipeItemValue(id) },
    async createRecipeItemValue(data) { const created = await AgriseedService.createRecipeItemValue(data); this.recipeItemValues.push(created); return created },
    async updateRecipeItemValue(id, data) { const updated = await AgriseedService.updateRecipeItemValue(id, data); const idx = this.recipeItemValues.findIndex(x=>x.id===id); if (idx !== -1) this.recipeItemValues.splice(idx,1,updated); return updated },
    async patchRecipeItemValue(id, data) { const patched = await AgriseedService.patchRecipeItemValue(id, data); const idx = this.recipeItemValues.findIndex(x=>x.id===id); if (idx !== -1) this.recipeItemValues.splice(idx,1,patched); return patched },
    async deleteRecipeItemValue(id) { await AgriseedService.removeRecipeItemValue(id); this.recipeItemValues = this.recipeItemValues.filter(x=>x.id!==id) },

    // Comments
    async fetchComments(params) { return await this._fetchCollection('comments', AgriseedService.listComments, params) },
    async createComment(data) { return await this._createItem('comments', AgriseedService.createComment, data) },
    async updateComment(id, data) { return await this._updateItem('comments', AgriseedService.updateComment, id, data) },
    async deleteComment(id) { return await this._deleteItem('comments', AgriseedService.removeComment, id) },

    // Performances
    async fetchPerformances(params) { return await this._fetchCollection('performances', AgriseedService.listPerformances, params) },
    async createPerformance(data) { return await this._createItem('performances', AgriseedService.createPerformance, data) },

    // Ratings
    async fetchRatings(params) { return await this._fetchCollection('ratings', AgriseedService.listRatings, params) },
    async createRating(data) { return await this._createItem('ratings', AgriseedService.createRating, data) }
  }
});
// 사용방법:
// 1. 컴포넌트에서 import 합니다: import { useCorecodeStore } from '@/services/corecode.store.js'
// 2. setup() 함수 내에서 스토어를 초기화합니다: const corecodeStore = useCorecodeStore();
// 3. 필요한 액션을 호출합니다: corecodeStore.fetchProjects({ page:1, ordering: '-id' });
// 4. state 데이터는 corecodeStore.projects 등에서 참조할 수 있습니다.

import { defineStore } from 'pinia';
import { CorecodeService } from './corecode.service';
import { normalizeList } from '@/utils/normalize';

// Common params: filtering and ordering via `params`, e.g. { project__id: 1, ordering: '-id' }
export const useCorecodeStore = defineStore('corecode', {
  state: () => ({
    projects: [],
    projectVersions: [],
    devices: [],
    companies: [],
    dataNames: [],
    dataNamesDict: {},
    controlLogics: [],
    controlLogicsDict: {},
    controlLogicsList: [],
    userPreferences: {},
    debugUsers: [],
    // 추가된 엔드포인트 캐시
    userManuals: [],
    controlValues: [],
    controlValueHistories: [],
    variables: [],
    memoryGroups: [],
    calcVariables: [],
    calcGroups: [],
    controlVariables: [],
    controlGroups: [],
    locationGroups: [],
    locationCodes: [],
    // 전역 로딩/에러 상태
    isLoading: false,
    lastError: null
  }),
  actions: {
    // Generic helpers for CRUD to reduce duplication and normalize lists
    async _fetchCollection(stateKey, listMethod, params) {
      this.isLoading = true; this.lastError = null;
      try {
        const res = await listMethod(params)
        const list = normalizeList(res)
        this[stateKey] = list
        return list
      } catch (error) {
        this.lastError = error; throw error
      } finally { this.isLoading = false }
    },
    async _getItem(getMethod, id) {
      this.isLoading = true; this.lastError = null;
      try { return await getMethod(id) } catch (error) { this.lastError = error; throw error } finally { this.isLoading = false }
    },
    async _createItem(stateKey, createMethod, data) {
      this.isLoading = true; this.lastError = null;
      try {
        const item = await createMethod(data)
        if (stateKey && Array.isArray(this[stateKey])) this[stateKey].push(item)
        return item
      } catch (error) { this.lastError = error; throw error } finally { this.isLoading = false }
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
      } catch (error) { this.lastError = error; throw error } finally { this.isLoading = false }
    },
    async _deleteItem(stateKey, deleteMethod, id) {
      this.isLoading = true; this.lastError = null;
      try {
        await deleteMethod(id)
        if (stateKey && Array.isArray(this[stateKey])) this[stateKey] = this[stateKey].filter(x => x.id !== id)
      } catch (error) { this.lastError = error; throw error } finally { this.isLoading = false }
    },

    // Projects
    async fetchProjects(params) { return await this._fetchCollection('projects', CorecodeService.listProjects, params) },
    async createProject(data) { return await this._createItem('projects', CorecodeService.createProject, data) },
    async updateProject(id, data) { return await this._updateItem('projects', CorecodeService.updateProject, id, data) },
    async deleteProject(id) { return await this._deleteItem('projects', CorecodeService.removeProject, id) },
    async restoreProjectVersion(projectId, version) { return await CorecodeService.restoreProjectVersion(projectId, version); },

    // Project Versions
    async fetchProjectVersions(params) { return await this._fetchCollection('projectVersions', CorecodeService.listProjectVersions, params) },
    async createProjectVersion(data) { return await this._createItem('projectVersions', CorecodeService.createProjectVersion, data) },
    async updateProjectVersion(id, data) { return await this._updateItem('projectVersions', CorecodeService.updateProjectVersion, id, data) },
    async deleteProjectVersion(id) { return await this._deleteItem('projectVersions', CorecodeService.removeProjectVersion, id) },

    // Devices
    async fetchDevices(params) { return await this._fetchCollection('devices', CorecodeService.listDevices, params) },
    async createDevice(data) { return await this._createItem('devices', CorecodeService.createDevice, data) },
    async updateDevice(id, data) { return await this._updateItem('devices', CorecodeService.updateDevice, id, data) },
    async deleteDevice(id) { return await this._deleteItem('devices', CorecodeService.removeDevice, id) },

    // Companies
    async fetchCompanies(params) { return await this._fetchCollection('companies', CorecodeService.listCompanies, params) },
    async getCompany(id) { return await this._getItem(CorecodeService.detailCompany, id) },
    async createCompany(data) { return await this._createItem('companies', CorecodeService.createCompany, data) },
    async updateCompany(id, data) { return await this._updateItem('companies', CorecodeService.updateCompany, id, data) },
    async patchCompany(id, data) { return await this._updateItem('companies', CorecodeService.patchCompany, id, data) },
    async deleteCompany(id) { return await this._deleteItem('companies', CorecodeService.removeCompany, id) },

    // DataNames
    async fetchDataNames(params) { return await this._fetchCollection('dataNames', CorecodeService.listDataNames, params) },
    async getDataName(id) { return await this._getItem(CorecodeService.detailDataName, id) },
    async createDataName(data) { return await this._createItem('dataNames', CorecodeService.createDataName, data) },
    async updateDataName(id, data) { return await this._updateItem('dataNames', CorecodeService.updateDataName, id, data) },
    async patchDataName(id, data) { return await this._updateItem('dataNames', CorecodeService.patchDataName, id, data) },
    async deleteDataName(id) { return await this._deleteItem('dataNames', CorecodeService.removeDataName, id) },
    async fetchDataNamesDict() { this.dataNamesDict = await CorecodeService.getDataNamesDict(); },

    // User Manuals
    async fetchUserManuals(params) { return await this._fetchCollection('userManuals', CorecodeService.listUserManuals, params) },
    async getUserManual(id) { return await this._getItem(CorecodeService.detailUserManual, id) },
    async createUserManual(data) { return await this._createItem('userManuals', CorecodeService.createUserManual, data) },
    async updateUserManual(id, data) { return await this._updateItem('userManuals', CorecodeService.updateUserManual, id, data) },
    async patchUserManual(id, data) { return await this._updateItem('userManuals', CorecodeService.patchUserManual, id, data) },
    async deleteUserManual(id) { return await this._deleteItem('userManuals', CorecodeService.removeUserManual, id) },

    // Control Values
    async fetchControlValues(params) { return await this._fetchCollection('controlValues', CorecodeService.listControlValues, params) },
    async getControlValue(id) { return await this._getItem(CorecodeService.detailControlValue, id) },
    async createControlValue(data) { return await this._createItem('controlValues', CorecodeService.createControlValue, data) },
    async updateControlValue(id, data) { return await this._updateItem('controlValues', CorecodeService.updateControlValue, id, data) },
    async patchControlValue(id, data) { return await this._updateItem('controlValues', CorecodeService.patchControlValue, id, data) },
    async deleteControlValue(id) { return await this._deleteItem('controlValues', CorecodeService.removeControlValue, id) },

    // Control Value Histories
    async fetchControlValueHistories(params) { return await this._fetchCollection('controlValueHistories', CorecodeService.listControlValueHistories, params) },
    async getControlValueHistory(id) { return await this._getItem(CorecodeService.detailControlValueHistory, id) },
    async createControlValueHistory(data) { return await this._createItem('controlValueHistories', CorecodeService.createControlValueHistory, data) },
    async updateControlValueHistory(id, data) { return await this._updateItem('controlValueHistories', CorecodeService.updateControlValueHistory, id, data) },
    async patchControlValueHistory(id, data) { return await this._updateItem('controlValueHistories', CorecodeService.patchControlValueHistory, id, data) },
    async deleteControlValueHistory(id) { return await this._deleteItem('controlValueHistories', CorecodeService.removeControlValueHistory, id) },

    // Variables / Memory Groups
    async fetchVariables(params) { return await this._fetchCollection('variables', CorecodeService.listVariables, params) },
    async getVariable(id) { return await this._getItem(CorecodeService.detailVariable, id) },
    async createVariable(data) { return await this._createItem('variables', CorecodeService.createVariable, data) },
    async updateVariable(id, data) { return await this._updateItem('variables', CorecodeService.updateVariable, id, data) },
    async patchVariable(id, data) { return await this._updateItem('variables', CorecodeService.patchVariable, id, data) },
    async deleteVariable(id) { return await this._deleteItem('variables', CorecodeService.removeVariable, id) },

    async fetchMemoryGroups(params) { return await this._fetchCollection('memoryGroups', CorecodeService.listMemoryGroups, params) },
    async getMemoryGroup(id) { return await this._getItem(CorecodeService.detailMemoryGroup, id) },
    async createMemoryGroup(data) { return await this._createItem('memoryGroups', CorecodeService.createMemoryGroup, data) },
    async updateMemoryGroup(id, data) { return await this._updateItem('memoryGroups', CorecodeService.updateMemoryGroup, id, data) },
    async patchMemoryGroup(id, data) { return await this._updateItem('memoryGroups', CorecodeService.patchMemoryGroup, id, data) },
    async deleteMemoryGroup(id) { return await this._deleteItem('memoryGroups', CorecodeService.removeMemoryGroup, id) },

    // Calc Variables / Groups
    async fetchCalcVariables(params) { return await this._fetchCollection('calcVariables', CorecodeService.listCalcVariables, params) },
    async getCalcVariable(id) { return await this._getItem(CorecodeService.detailCalcVariable, id) },
    async createCalcVariable(data) { return await this._createItem('calcVariables', CorecodeService.createCalcVariable, data) },
    async updateCalcVariable(id, data) { return await this._updateItem('calcVariables', CorecodeService.updateCalcVariable, id, data) },
    async patchCalcVariable(id, data) { return await this._updateItem('calcVariables', CorecodeService.patchCalcVariable, id, data) },
    async deleteCalcVariable(id) { return await this._deleteItem('calcVariables', CorecodeService.removeCalcVariable, id) },

    async fetchCalcGroups(params) { return await this._fetchCollection('calcGroups', CorecodeService.listCalcGroups, params) },
    async getCalcGroup(id) { return await this._getItem(CorecodeService.detailCalcGroup, id) },
    async createCalcGroup(data) { return await this._createItem('calcGroups', CorecodeService.createCalcGroup, data) },
    async updateCalcGroup(id, data) { return await this._updateItem('calcGroups', CorecodeService.updateCalcGroup, id, data) },
    async patchCalcGroup(id, data) { return await this._updateItem('calcGroups', CorecodeService.patchCalcGroup, id, data) },
    async deleteCalcGroup(id) { return await this._deleteItem('calcGroups', CorecodeService.removeCalcGroup, id) },

    // Control Variables / Groups
    async fetchControlVariables(params) { return await this._fetchCollection('controlVariables', CorecodeService.listControlVariables, params) },
    async getControlVariable(id) { return await this._getItem(CorecodeService.detailControlVariable, id) },
    async createControlVariable(data) { return await this._createItem('controlVariables', CorecodeService.createControlVariable, data) },
    async updateControlVariable(id, data) { return await this._updateItem('controlVariables', CorecodeService.updateControlVariable, id, data) },
    async patchControlVariable(id, data) { return await this._updateItem('controlVariables', CorecodeService.patchControlVariable, id, data) },
    async deleteControlVariable(id) { return await this._deleteItem('controlVariables', CorecodeService.removeControlVariable, id) },

    async fetchControlGroups(params) { return await this._fetchCollection('controlGroups', CorecodeService.listControlGroups, params) },
    async getControlGroup(id) { return await this._getItem(CorecodeService.detailControlGroup, id) },
    async createControlGroup(data) { return await this._createItem('controlGroups', CorecodeService.createControlGroup, data) },
    async updateControlGroup(id, data) { return await this._updateItem('controlGroups', CorecodeService.updateControlGroup, id, data) },
    async patchControlGroup(id, data) { return await this._updateItem('controlGroups', CorecodeService.patchControlGroup, id, data) },
    async deleteControlGroup(id) { return await this._deleteItem('controlGroups', CorecodeService.removeControlGroup, id) },

    // Location Groups / Codes
    async fetchLocationGroups(params) { return await this._fetchCollection('locationGroups', CorecodeService.listLocationGroups, params) },
    async getLocationGroup(id) { return await this._getItem(CorecodeService.detailLocationGroup, id) },
    async createLocationGroup(data) { return await this._createItem('locationGroups', CorecodeService.createLocationGroup, data) },
    async updateLocationGroup(id, data) { return await this._updateItem('locationGroups', CorecodeService.updateLocationGroup, id, data) },
    async patchLocationGroup(id, data) { return await this._updateItem('locationGroups', CorecodeService.patchLocationGroup, id, data) },
    async deleteLocationGroup(id) { return await this._deleteItem('locationGroups', CorecodeService.removeLocationGroup, id) },

    async fetchLocationCodes(params) { return await this._fetchCollection('locationCodes', CorecodeService.listLocationCodes, params) },
    async getLocationCode(id) { return await this._getItem(CorecodeService.detailLocationCode, id) },
    async createLocationCode(data) { return await this._createItem('locationCodes', CorecodeService.createLocationCode, data) },
    async updateLocationCode(id, data) { return await this._updateItem('locationCodes', CorecodeService.updateLocationCode, id, data) },
    async patchLocationCode(id, data) { return await this._updateItem('locationCodes', CorecodeService.patchLocationCode, id, data) },
    async deleteLocationCode(id) { return await this._deleteItem('locationCodes', CorecodeService.removeLocationCode, id) },

    // User Preferences
    async fetchUserPreferences(username) { this.userPreferences = await CorecodeService.getPreferences(username); },
    async updateUserPreferences(username, data) { return await CorecodeService.updatePreferences(username, data); },
    async patchUserPreferences(username, data) { return await CorecodeService.patchPreferences(username, data); },

    // Debug Users
    async fetchDebugUsers(params) { return await this._fetchCollection('debugUsers', CorecodeService.listUsersDebug, params) }
  }
});
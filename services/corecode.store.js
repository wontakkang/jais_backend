// 사용방법:
// 1. 컴포넌트에서 import 합니다: import { useCorecodeStore } from '@/services/corecode.store.js'
// 2. setup() 함수 내에서 스토어를 초기화합니다: const corecodeStore = useCorecodeStore();
// 3. 필요한 액션을 호출합니다: corecodeStore.fetchProjects({ page:1, ordering: '-id' });
// 4. state 데이터는 corecodeStore.projects 등에서 참조할 수 있습니다.

import { defineStore } from 'pinia';
import { CorecodeService } from './corecode.service';
import { showToast } from '@/utils/domUtils';
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
    debugUsers: []
  }),
  actions: {
    // Projects
    async fetchProjects(params) { this.projects = await CorecodeService.listProjects(params); },
    async createProject(data) { const p = await CorecodeService.createProject(data); this.projects.push(p); return p; },
    async updateProject(id, data) { const u = await CorecodeService.updateProject(id, data); const i = this.projects.findIndex(x => x.id === id); if (i !== -1) this.projects.splice(i,1,u); return u; },
    async deleteProject(id) { await CorecodeService.removeProject(id); this.projects = this.projects.filter(x => x.id !== id); },
    async restoreProjectVersion(projectId, version) { return await CorecodeService.restoreProjectVersion(projectId, version); },

    // Project Versions
    async fetchProjectVersions(params) { this.projectVersions = await CorecodeService.listProjectVersions(params); },
    async createProjectVersion(data) { const v = await CorecodeService.createProjectVersion(data); this.projectVersions.push(v); return v; },
    async updateProjectVersion(id, data) { const u = await CorecodeService.updateProjectVersion(id, data); const i = this.projectVersions.findIndex(x => x.id === id); if (i !== -1) this.projectVersions.splice(i,1,u); return u; },
    async deleteProjectVersion(id) { await CorecodeService.removeProjectVersion(id); this.projectVersions = this.projectVersions.filter(x => x.id !== id); },

    // Devices
    async fetchDevices(params) { this.devices = await CorecodeService.listDevices(params); },
    async createDevice(data) { const d = await CorecodeService.createDevice(data); this.devices.push(d); return d; },
    async updateDevice(id, data) { const u = await CorecodeService.updateDevice(id, data); const i = this.devices.findIndex(x => x.id === id); if (i !== -1) this.devices.splice(i,1,u); return u; },
    async deleteDevice(id) { await CorecodeService.removeDevice(id); this.devices = this.devices.filter(x => x.id !== id); },

    // Companies
    async fetchCompanies(params) { this.companies = await CorecodeService.listCompanies(params); },

    // DataNames
    async fetchDataNames(params) { this.dataNames = await CorecodeService.listDataNames(params); },
    async fetchDataNamesDict() { this.dataNamesDict = await CorecodeService.getDataNamesDict(); },

    // ControlLogics
    async fetchControlLogics(params) { this.controlLogics = await CorecodeService.listControlLogics(params); },
    async fetchControlLogicsDict() { this.controlLogicsDict = await CorecodeService.getControlLogicsDict(); },
    async fetchControlLogicsList() { this.controlLogicsList = await CorecodeService.listControlLogicsList(); },

    // User Preferences
    async fetchUserPreferences(username) { this.userPreferences = await CorecodeService.getPreferences(username); },
    async updateUserPreferences(username, data) { return await CorecodeService.updatePreferences(username, data); },
    async patchUserPreferences(username, data) { return await CorecodeService.patchPreferences(username, data); },

    // Debug Users
    async fetchDebugUsers(params) { this.debugUsers = await CorecodeService.listUsersDebug(params); }
  }
});
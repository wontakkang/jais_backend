import api from '@/utils/apiClient'
import { showToast, formatApiError } from '@/utils/domUtils';
import { buildDjangoFilterParams } from '@/utils/django-filter.js';
import { normalizeData } from '@/utils/normalize.js';

// Common usage: pass a `params` object to list methods for filtering and ordering, e.g. { status: 'active', ordering: '-id' }
export const CorecodeService = {
  // Projects
  async listProjects(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/projects/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 목록을 불러오는 중 오류가 발생했습니다.'), 5000);
      throw error;
    }
  },

  async detailProject(id) {
    try {
      const res = await api.get(`/corecode/projects/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 상세 정보를 가져오는 중 오류가 발생했습니다.'), 5000);
      throw error;
    }
  },

  async createProject(payload) {
    try {
      const res = await api.post('/corecode/projects/', payload);
      showToast('프로젝트가 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 생성에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async updateProject(id, payload) {
    try {
      const res = await api.put(`/corecode/projects/${id}/`, payload);
      showToast('프로젝트가 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 업데이트에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async patchProject(id, payload) {
    try {
      const res = await api.patch(`/corecode/projects/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 패치에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async removeProject(id) {
    try {
      await api.delete(`/corecode/projects/${id}/`);
      showToast('프로젝트가 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 삭제에 실패했습니다.'), 5000);
      throw error;
    }
  },

  // Project Versions
  async listProjectVersions(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/project-versions/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 버전 목록을 불러오는 중 오류가 발생했습니다.'), 5000);
      throw error;
    }
  },

  async detailProjectVersion(id) {
    try {
      const res = await api.get(`/corecode/project-versions/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 버전 상세 정보를 가져오는 중 오류가 발생했습니다.'), 5000);
      throw error;
    }
  },

  async createProjectVersion(payload) {
    try {
      const res = await api.post('/corecode/project-versions/', payload);
      showToast('프로젝트 버전이 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 버전 생성에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async updateProjectVersion(id, payload) {
    try {
      const res = await api.put(`/corecode/project-versions/${id}/`, payload);
      showToast('프로젝트 버전이 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 버전 업데이트에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async patchProjectVersion(id, payload) {
    try {
      const res = await api.patch(`/corecode/project-versions/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 버전 패치에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async removeProjectVersion(id) {
    try {
      await api.delete(`/corecode/project-versions/${id}/`);
      showToast('프로젝트 버전이 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 버전 삭제에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async restoreProjectVersion(projectId, version) {
    try {
      const res = await api.post(`/corecode/projects/${projectId}/restore/${version}/`);
      showToast('프로젝트 버전이 복원되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '프로젝트 버전 복원에 실패했습니다.'), 5000);
      throw error;
    }
  },

  // Devices
  async listDevices(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/devices/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '디바이스 목록을 불러오는 중 오류가 발생했습니다.'), 5000);
      throw error;
    }
  },

  async detailDevice(id) {
    try {
      const res = await api.get(`/corecode/devices/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '디바이스 상세 정보를 가져오는 중 오류가 발생했습니다.'), 5000);
      throw error;
    }
  },

  async createDevice(payload) {
    try {
      const res = await api.post('/corecode/devices/', payload);
      showToast('디바이스가 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '디바이스 생성에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async updateDevice(id, payload) {
    try {
      const res = await api.put(`/corecode/devices/${id}/`, payload);
      showToast('디바이스가 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '디바이스 업데이트에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async patchDevice(id, payload) {
    try {
      const res = await api.patch(`/corecode/devices/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '디바이스 패치에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async removeDevice(id) {
    try {
      await api.delete(`/corecode/devices/${id}/`);
      showToast('디바이스가 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '디바이스 삭제에 실패했습니다.'), 5000);
      throw error;
    }
  },

  // Companies
  async listCompanies(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/companies/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '회사 목록을 불러오는 중 오류가 발생했습니다.'), 5000);
      throw error;
    }
  },

  async detailCompany(id) {
    try {
      const res = await api.get(`/corecode/companies/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '회사 상세 정보를 가져오는 중 오류가 발생했습니다.'), 5000);
      throw error;
    }
  },

  async createCompany(payload) {
    try {
      const res = await api.post('/corecode/companies/', payload);
      showToast('회사 정보가 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '회사 생성에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async updateCompany(id, payload) {
    try {
      const res = await api.put(`/corecode/companies/${id}/`, payload);
      showToast('회사 정보가 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '회사 업데이트에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async patchCompany(id, payload) {
    try {
      const res = await api.patch(`/corecode/companies/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '회사 정보 패치에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async removeCompany(id) {
    try {
      await api.delete(`/corecode/companies/${id}/`);
      showToast('회사 정보가 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '회사 삭제에 실패했습니다.'), 5000);
      throw error;
    }
  },

  // DataNames
  async listDataNames(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/data-names/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '데이터 이름 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async getDataNamesDict() {
    try {
      const res = await api.get('/corecode/data-names/dict/');
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '데이터 이름 딕셔너리 로드 실패'), 5000);
      throw error;
    }
  },
  async detailDataName(id) {
    try {
      const res = await api.get(`/corecode/data-names/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '데이터 이름 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createDataName(payload) {
    try {
      const res = await api.post('/corecode/data-names/', payload);
      showToast('데이터 이름이 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '데이터 이름 생성 실패'), 5000);
      throw error;
    }
  },
  async updateDataName(id, payload) {
    try {
      const res = await api.put(`/corecode/data-names/${id}/`, payload);
      showToast('데이터 이름이 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '데이터 이름 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchDataName(id, payload) {
    try {
      const res = await api.patch(`/corecode/data-names/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '데이터 이름 패치 실패'), 5000);
      throw error;
    }
  },
  async removeDataName(id) {
    try {
      await api.delete(`/corecode/data-names/${id}/`);
      showToast('데이터 이름이 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '데이터 이름 삭제 실패'), 5000);
      throw error;
    }
  },

  // Control Logics
  async listControlLogics(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/control-logics/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '제어 로직 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async getControlLogicsDict() {
    try {
      const res = await api.get('/corecode/control-logics/dict/');
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 로직 딕셔너리 로드 실패'), 5000);
      throw error;
    }
  },
  async listControlLogicsList(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/control-logics/dict/?type=list', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '제어 로직 리스트 로드 실패'), 5000);
      throw error;
    }
  },
  async detailControlLogic(id) {
    try {
      const res = await api.get(`/corecode/control-logics/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 로직 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createControlLogic(payload) {
    try {
      const res = await api.post('/corecode/control-logics/', payload);
      showToast('제어 로직이 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 로직 생성 실패'), 5000);
      throw error;
    }
  },
  async updateControlLogic(id, payload) {
    try {
      const res = await api.put(`/corecode/control-logics/${id}/`, payload);
      showToast('제어 로직이 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 로직 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchControlLogic(id, payload) {
    try {
      const res = await api.patch(`/corecode/control-logics/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 로직 패치 실패'), 5000);
      throw error;
    }
  },
  async removeControlLogic(id) {
    try {
      await api.delete(`/corecode/control-logics/${id}/`);
      showToast('제어 로직이 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '제어 로직 삭제 실패'), 5000);
      throw error;
    }
  },

  // User Preferences
  async getPreferences(username) {
    try {
      const res = await api.get(`/corecode/user-preferences/${username}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '사용자 환경설정을 가져오는 중 오류가 발생했습니다.'), 5000);
      throw error;
    }
  },

  async updatePreferences(username, payload) {
    try {
      const res = await api.put(`/corecode/user-preferences/${username}/`, payload);
      showToast('사용자 환경설정이 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '사용자 환경설정 업데이트에 실패했습니다.'), 5000);
      throw error;
    }
  },

  async patchPreferences(username, payload) {
    try {
      const res = await api.patch(`/corecode/user-preferences/${username}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '사용자 환경설정 패치에 실패했습니다.'), 5000);
      throw error;
    }
  },

  // Debug user list
  async listUsersDebug(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/users-debug/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '디버그 사용자 목록을 불러오는 중 오류가 발생했습니다.'), 5000);
      throw error;
    }
  },

  // User Manuals
  async listUserManuals(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/user-manuals/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '사용자 매뉴얼 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async detailUserManual(id) {
    try {
      const res = await api.get(`/corecode/user-manuals/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '사용자 매뉴얼 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createUserManual(payload) {
    try {
      const res = await api.post('/corecode/user-manuals/', payload);
      showToast('사용자 매뉴얼이 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '사용자 매뉴얼 생성 실패'), 5000);
      throw error;
    }
  },
  async updateUserManual(id, payload) {
    try {
      const res = await api.put(`/corecode/user-manuals/${id}/`, payload);
      showToast('사용자 매뉴얼이 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '사용자 매뉴얼 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchUserManual(id, payload) {
    try {
      const res = await api.patch(`/corecode/user-manuals/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '사용자 매뉴얼 패치 실패'), 5000);
      throw error;
    }
  },
  async removeUserManual(id) {
    try {
      await api.delete(`/corecode/user-manuals/${id}/`);
      showToast('사용자 매뉴얼이 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '사용자 매뉴얼 삭제 실패'), 5000);
      throw error;
    }
  },

  // Control Values
  async listControlValues(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/control-values/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '제어값 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async detailControlValue(id) {
    try {
      const res = await api.get(`/corecode/control-values/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어값 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createControlValue(payload) {
    try {
      const res = await api.post('/corecode/control-values/', payload);
      showToast('제어값이 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어값 생성 실패'), 5000);
      throw error;
    }
  },
  async updateControlValue(id, payload) {
    try {
      const res = await api.put(`/corecode/control-values/${id}/`, payload);
      showToast('제어값이 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어값 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchControlValue(id, payload) {
    try {
      const res = await api.patch(`/corecode/control-values/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어값 패치 실패'), 5000);
      throw error;
    }
  },
  async removeControlValue(id) {
    try {
      await api.delete(`/corecode/control-values/${id}/`);
      showToast('제어값이 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '제어값 삭제 실패'), 5000);
      throw error;
    }
  },
  // Control Value Histories
  async listControlValueHistories(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/control-value-histories/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '제어값 이력 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async detailControlValueHistory(id) {
    try {
      const res = await api.get(`/corecode/control-value-histories/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어값 이력 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createControlValueHistory(payload) {
    try {
      const res = await api.post('/corecode/control-value-histories/', payload);
      showToast('제어값 이력이 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어값 이력 생성 실패'), 5000);
      throw error;
    }
  },
  async updateControlValueHistory(id, payload) {
    try {
      const res = await api.put(`/corecode/control-value-histories/${id}/`, payload);
      showToast('제어값 이력이 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어값 이력 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchControlValueHistory(id, payload) {
    try {
      const res = await api.patch(`/corecode/control-value-histories/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어값 이력 패치 실패'), 5000);
      throw error;
    }
  },
  async removeControlValueHistory(id) {
    try {
      await api.delete(`/corecode/control-value-histories/${id}/`);
      showToast('제어값 이력이 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '제어값 이력 삭제 실패'), 5000);
      throw error;
    }
  },
  // Variables
  async listVariables(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/variables/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '변수 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async detailVariable(id) {
    try {
      const res = await api.get(`/corecode/variables/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '변수 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createVariable(payload) {
    try {
      const res = await api.post('/corecode/variables/', payload);
      showToast('변수가 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '변수 생성 실패'), 5000);
      throw error;
    }
  },
  async updateVariable(id, payload) {
    try {
      const res = await api.put(`/corecode/variables/${id}/`, payload);
      showToast('변수가 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '변수 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchVariable(id, payload) {
    try {
      const res = await api.patch(`/corecode/variables/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '변수 패치 실패'), 5000);
      throw error;
    }
  },
  async removeVariable(id) {
    try {
      await api.delete(`/corecode/variables/${id}/`);
      showToast('변수가 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '변수 삭제 실패'), 5000);
      throw error;
    }
  },
  // Memory Groups
  async listMemoryGroups(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/memory-groups/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '메모리 그룹 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async detailMemoryGroup(id) {
    try {
      const res = await api.get(`/corecode/memory-groups/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '메모리 그룹 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createMemoryGroup(payload) {
    try {
      const res = await api.post('/corecode/memory-groups/', payload);
      showToast('메모리 그룹이 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '메모리 그룹 생성 실패'), 5000);
      throw error;
    }
  },
  async updateMemoryGroup(id, payload) {
    try {
      const res = await api.put(`/corecode/memory-groups/${id}/`, payload);
      showToast('메모리 그룹이 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '메모리 그룹 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchMemoryGroup(id, payload) {
    try {
      const res = await api.patch(`/corecode/memory-groups/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '메모리 그룹 패치 실패'), 5000);
      throw error;
    }
  },
  async removeMemoryGroup(id) {
    try {
      await api.delete(`/corecode/memory-groups/${id}/`);
      showToast('메모리 그룹이 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '메모리 그룹 삭제 실패'), 5000);
      throw error;
    }
  },
  // Calc Variables
  async listCalcVariables(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/calc-variables/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '계산 변수 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async detailCalcVariable(id) {
    try {
      const res = await api.get(`/corecode/calc-variables/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '계산 변수 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createCalcVariable(payload) {
    try {
      const res = await api.post('/corecode/calc-variables/', payload);
      showToast('계산 변수가 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '계산 변수 생성 실패'), 5000);
      throw error;
    }
  },
  async updateCalcVariable(id, payload) {
    try {
      const res = await api.put(`/corecode/calc-variables/${id}/`, payload);
      showToast('계산 변수가 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '계산 변수 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchCalcVariable(id, payload) {
    try {
      const res = await api.patch(`/corecode/calc-variables/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '계산 변수 패치 실패'), 5000);
      throw error;
    }
  },
  async removeCalcVariable(id) {
    try {
      await api.delete(`/corecode/calc-variables/${id}/`);
      showToast('계산 변수가 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '계산 변수 삭제 실패'), 5000);
      throw error;
    }
  },

  // Calc Groups
  async listCalcGroups(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/calc-groups/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '계산 그룹 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async detailCalcGroup(id) {
    try {
      const res = await api.get(`/corecode/calc-groups/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '계산 그룹 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createCalcGroup(payload) {
    try {
      const res = await api.post('/corecode/calc-groups/', payload);
      showToast('계산 그룹이 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '계산 그룹 생성 실패'), 5000);
      throw error;
    }
  },
  async updateCalcGroup(id, payload) {
    try {
      const res = await api.put(`/corecode/calc-groups/${id}/`, payload);
      showToast('계산 그룹이 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '계산 그룹 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchCalcGroup(id, payload) {
    try {
      const res = await api.patch(`/corecode/calc-groups/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '계산 그룹 패치 실패'), 5000);
      throw error;
    }
  },
  async removeCalcGroup(id) {
    try {
      await api.delete(`/corecode/calc-groups/${id}/`);
      showToast('계산 그룹이 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '계산 그룹 삭제 실패'), 5000);
      throw error;
    }
  },

  // Control Variables
  async listControlVariables(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/control-variables/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '제어 변수 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async detailControlVariable(id) {
    try {
      const res = await api.get(`/corecode/control-variables/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 변수 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createControlVariable(payload) {
    try {
      const res = await api.post('/corecode/control-variables/', payload);
      showToast('제어 변수가 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 변수 생성 실패'), 5000);
      throw error;
    }
  },
  async updateControlVariable(id, payload) {
    try {
      const res = await api.put(`/corecode/control-variables/${id}/`, payload);
      showToast('제어 변수가 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 변수 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchControlVariable(id, payload) {
    try {
      const res = await api.patch(`/corecode/control-variables/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 변수 패치 실패'), 5000);
      throw error;
    }
  },
  async removeControlVariable(id) {
    try {
      await api.delete(`/corecode/control-variables/${id}/`);
      showToast('제어 변수가 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '제어 변수 삭제 실패'), 5000);
      throw error;
    }
  },

  // Control Groups
  async listControlGroups(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/control-groups/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '제어 그룹 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async detailControlGroup(id) {
    try {
      const res = await api.get(`/corecode/control-groups/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 그룹 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createControlGroup(payload) {
    try {
      const res = await api.post('/corecode/control-groups/', payload);
      showToast('제어 그룹이 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 그룹 생성 실패'), 5000);
      throw error;
    }
  },
  async updateControlGroup(id, payload) {
    try {
      const res = await api.put(`/corecode/control-groups/${id}/`, payload);
      showToast('제어 그룹이 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 그룹 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchControlGroup(id, payload) {
    try {
      const res = await api.patch(`/corecode/control-groups/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '제어 그룹 패치 실패'), 5000);
      throw error;
    }
  },
  async removeControlGroup(id) {
    try {
      await api.delete(`/corecode/control-groups/${id}/`);
      showToast('제어 그룹이 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '제어 그룹 삭제 실패'), 5000);
      throw error;
    }
  },

  // Location Groups
  async listLocationGroups(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/location-groups/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '위치 그룹 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async detailLocationGroup(id) {
    try {
      const res = await api.get(`/corecode/location-groups/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '위치 그룹 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createLocationGroup(payload) {
    try {
      const res = await api.post('/corecode/location-groups/', payload);
      showToast('위치 그룹이 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '위치 그룹 생성 실패'), 5000);
      throw error;
    }
  },
  async updateLocationGroup(id, payload) {
    try {
      const res = await api.put(`/corecode/location-groups/${id}/`, payload);
      showToast('위치 그룹이 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '위치 그룹 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchLocationGroup(id, payload) {
    try {
      const res = await api.patch(`/corecode/location-groups/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '위치 그룹 패치 실패'), 5000);
      throw error;
    }
  },
  async removeLocationGroup(id) {
    try {
      await api.delete(`/corecode/location-groups/${id}/`);
      showToast('위치 그룹이 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '위치 그룹 삭제 실패'), 5000);
      throw error;
    }
  },

  // Location Codes
  async listLocationCodes(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/corecode/location-codes/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast(formatApiError(error, '위치 코드 목록 로드 실패'), 5000);
      throw error;
    }
  },
  async detailLocationCode(id) {
    try {
      const res = await api.get(`/corecode/location-codes/${id}/`);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '위치 코드 상세 로드 실패'), 5000);
      throw error;
    }
  },
  async createLocationCode(payload) {
    try {
      const res = await api.post('/corecode/location-codes/', payload);
      showToast('위치 코드가 생성되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '위치 코드 생성 실패'), 5000);
      throw error;
    }
  },
  async updateLocationCode(id, payload) {
    try {
      const res = await api.put(`/corecode/location-codes/${id}/`, payload);
      showToast('위치 코드가 업데이트되었습니다.', 3000);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '위치 코드 업데이트 실패'), 5000);
      throw error;
    }
  },
  async patchLocationCode(id, payload) {
    try {
      const res = await api.patch(`/corecode/location-codes/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast(formatApiError(error, '위치 코드 패치 실패'), 5000);
      throw error;
    }
  },
  async removeLocationCode(id) {
    try {
      await api.delete(`/corecode/location-codes/${id}/`);
      showToast('위치 코드가 삭제되었습니다.', 3000);
    } catch (error) {
      showToast(formatApiError(error, '위치 코드 삭제 실패'), 5000);
      throw error;
    }
  }
};
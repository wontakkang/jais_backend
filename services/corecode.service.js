import axios from "axios";
import { showToast } from '@/utils/domUtils';
import { buildDjangoFilterParams } from '@/utils/django-filter.js';

// 응답 정규화 헬퍼
function normalizeData(data, responseType = 'original', wrapSingle = false) {
  const type = (responseType || 'original').toString().toLowerCase();
  const isArray = Array.isArray(data);
  const results = data && Array.isArray(data.results) ? data.results : (data && Array.isArray(data.data) ? data.data : null);
  if (type === 'original') return data;
  if (type === 'array' || type === 'list') {
    if (isArray) return data;
    if (results) return results;
    if (data && typeof data === 'object') return wrapSingle ? [data] : [];
    return [];
  }
  if (type === 'object' || type === 'dict') {
    if (!isArray && data && typeof data === 'object') return data;
    if (isArray) return data.length ? data[0] : null;
    if (results && results.length) return results[0];
    return null;
  }
  return data;
}

// Common usage: pass a `params` object to list methods for filtering and ordering, e.g. { status: 'active', ordering: '-id' }
export const CorecodeService = {
  // Projects
  async listProjects(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/corecode/projects/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('프로젝트 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },

  async detailProject(id) {
    try {
      const res = await axios.get(`/corecode/projects/${id}/`);
      return res.data;
    } catch (error) {
      showToast('프로젝트 상세 정보를 가져오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },

  async createProject(payload) {
    try {
      const res = await axios.post('/corecode/projects/', payload);
      showToast('프로젝트가 생성되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('프로젝트 생성에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async updateProject(id, payload) {
    try {
      const res = await axios.put(`/corecode/projects/${id}/`, payload);
      showToast('프로젝트가 업데이트되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('프로젝트 업데이트에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async patchProject(id, payload) {
    try {
      const res = await axios.patch(`/corecode/projects/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast('프로젝트 패치에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async removeProject(id) {
    try {
      await axios.delete(`/corecode/projects/${id}/`);
      showToast('프로젝트가 삭제되었습니다.', 3000, 'success');
    } catch (error) {
      showToast('프로젝트 삭제에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  // Project Versions
  async listProjectVersions(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/corecode/project-versions/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('프로젝트 버전 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },

  async detailProjectVersion(id) {
    try {
      const res = await axios.get(`/corecode/project-versions/${id}/`);
      return res.data;
    } catch (error) {
      showToast('프로젝트 버전 상세 정보를 가져오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },

  async createProjectVersion(payload) {
    try {
      const res = await axios.post('/corecode/project-versions/', payload);
      showToast('프로젝트 버전이 생성되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('프로젝트 버전 생성에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async updateProjectVersion(id, payload) {
    try {
      const res = await axios.put(`/corecode/project-versions/${id}/`, payload);
      showToast('프로젝트 버전이 업데이트되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('프로젝트 버전 업데이트에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async patchProjectVersion(id, payload) {
    try {
      const res = await axios.patch(`/corecode/project-versions/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast('프로젝트 버전 패치에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async removeProjectVersion(id) {
    try {
      await axios.delete(`/corecode/project-versions/${id}/`);
      showToast('프로젝트 버전이 삭제되었습니다.', 3000, 'success');
    } catch (error) {
      showToast('프로젝트 버전 삭제에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async restoreProjectVersion(projectId, version) {
    try {
      const res = await axios.post(`/corecode/projects/${projectId}/restore/${version}/`);
      showToast('프로젝트 버전이 복원되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('프로젝트 버전 복원에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  // Devices
  async listDevices(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/corecode/devices/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('디바이스 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },

  async detailDevice(id) {
    try {
      const res = await axios.get(`/corecode/devices/${id}/`);
      return res.data;
    } catch (error) {
      showToast('디바이스 상세 정보를 가져오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },

  async createDevice(payload) {
    try {
      const res = await axios.post('/corecode/devices/', payload);
      showToast('디바이스가 생성되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('디바이스 생성에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async updateDevice(id, payload) {
    try {
      const res = await axios.put(`/corecode/devices/${id}/`, payload);
      showToast('디바이스가 업데이트되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('디바이스 업데이트에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async patchDevice(id, payload) {
    try {
      const res = await axios.patch(`/corecode/devices/${id}/`, payload);
      return res.data;
    } catch (error) {
      showToast('디바이스 패치에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async removeDevice(id) {
    try {
      await axios.delete(`/corecode/devices/${id}/`);
      showToast('디바이스가 삭제되었습니다.', 3000, 'success');
    } catch (error) {
      showToast('디바이스 삭제에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  // Companies
  async listCompanies(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/corecode/companies/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('회사 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },

  // DataNames
  async listDataNames(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/corecode/data-names/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('데이터 이름 목록 로드 실패', 3000, 'error');
      throw error;
    }
  },
  async getDataNamesDict() {
    try {
      const res = await axios.get('/corecode/data-names/dict/');
      return res.data;
    } catch (error) {
      showToast('데이터 이름 딕셔너리 로드 실패', 3000, 'error');
      throw error;
    }
  },

  // Control Logics
  async listControlLogics(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/corecode/control-logics/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('제어 로직 목록 로드 실패', 3000, 'error');
      throw error;
    }
  },
  async getControlLogicsDict() {
    try {
      const res = await axios.get('/corecode/control-logics/dict/');
      return res.data;
    } catch (error) {
      showToast('제어 로직 딕셔너리 로드 실패', 3000, 'error');
      throw error;
    }
  },
  async listControlLogicsList(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const qp = query instanceof URLSearchParams ? query : new URLSearchParams(query)
      qp.append('type', 'list')
      const res = await axios.get('/corecode/control-logics/dict/', { params: qp });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('제어 로직 리스트 로드 실패', 3000, 'error');
      throw error;
    }
  },

  // User Preferences
  async getPreferences(username) {
    try {
      const res = await axios.get(`/corecode/user-preferences/${username}/`);
      return res.data;
    } catch (error) {
      showToast('사용자 환경설정을 가져오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },

  async updatePreferences(username, payload) {
    try {
      const res = await axios.put(`/corecode/user-preferences/${username}/`, payload);
      showToast('사용자 환경설정이 업데이트되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('사용자 환경설정 업데이트에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async patchPreferences(username, payload) {
    try {
      const res = await axios.patch(`/corecode/user-preferences/${username}/`, payload);
      return res.data;
    } catch (error) {
      showToast('사용자 환경설정 패치에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  // Debug user list
  async listUsersDebug(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/corecode/users-debug/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('디버그 사용자 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  }
};
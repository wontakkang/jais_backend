import axios from "axios";
import { showToast } from '@/utils/domUtils';
import { buildDjangoFilterParams } from '@/utils/django-filter.js';

// 표준 토스트 설정
const TOAST = {
  SUCCESS_DURATION: 3000,
  ERROR_DURATION: 5000
};

function apiToast(message, type = 'error') {
  const duration = type === 'success' ? TOAST.SUCCESS_DURATION : TOAST.ERROR_DURATION;
  showToast(message, duration, type);
}

// 응답 정규화 헬퍼
function normalizeData(data, responseType = 'original', wrapSingle = false) {
  // responseType aliases: 'array'|'list' -> array, 'object'|'dict' -> object, 'original' -> raw
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

  // fallback: return original
  return data;
}

// Common usage: pass a `params` object to list methods for filtering and ordering, e.g. { status: 'active', ordering: '-id' }
export const AgriseedService = {
  async listDevices(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/agriseed/devices/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('디바이스 목록을 불러오는 중 오류가 발생했습니다.', 'error');
      throw error;
    }
  },

  async detailDevice(id) {
    try {
      const res = await axios.get(`/agriseed/devices/${id}/`);
      return res.data;
    } catch (error) {
      apiToast('디바이스 상세 정보를 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createDevice(payload) {
    try {
      const res = await axios.post('/agriseed/devices/', payload);
      apiToast('디바이스 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('디바이스 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async updateDevice(id, payload) {
    try {
      const res = await axios.put(`/agriseed/devices/${id}/`, payload);
      apiToast('디바이스 정보 업데이트에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('디바이스 업데이트에 실패했습니다.', 'error');
      throw error;
    }
  },

  async patchDevice(id, payload) {
    try {
      const res = await axios.patch(`/agriseed/devices/${id}/`, payload);
      apiToast('디바이스 정보 부분 수정에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('디바이스 정보 부분 수정에 실패했습니다.', 'error');
      throw error;
    }
  },

  async removeDevice(id) {
    try {
      await axios.delete(`/agriseed/devices/${id}/`);
      apiToast('디바이스 삭제에 성공했습니다.', 'success');
    } catch (error) {
      apiToast('디바이스 삭제에 실패했습니다.', 'error');
      throw error;
    }
  },

  async listActivities(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/agriseed/activities/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('활동 목록을 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async detailActivity(id) {
    try {
      const res = await axios.get(`/agriseed/activities/${id}/`);
      return res.data;
    } catch (error) {
      apiToast('활동 상세 정보를 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createActivity(payload) {
    try {
      const res = await axios.post('/agriseed/activities/', payload);
      apiToast('활동 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('활동 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async updateActivity(id, payload) {
    try {
      const res = await axios.put(`/agriseed/activities/${id}/`, payload);
      apiToast('활동 업데이트에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('활동 업데이트에 실패했습니다.', 'error');
      throw error;
    }
  },

  async patchActivity(id, payload) {
    try {
      const res = await axios.patch(`/agriseed/activities/${id}/`, payload);
      apiToast('활동 수정에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('활동 수정에 실패했습니다.', 'error');
      throw error;
    }
  },

  async removeActivity(id) {
    try {
      await axios.delete(`/agriseed/activities/${id}/`);
      apiToast('활동 삭제에 성공했습니다.', 'success');
    } catch (error) {
      apiToast('활동 삭제에 실패했습니다.', 'error');
      throw error;
    }
  },

  async listRecipes(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/agriseed/recipe-profiles/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('레시피 목록을 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async detailRecipe(id) {
    try {
      const res = await axios.get(`/agriseed/recipe-profiles/${id}/`);
      return res.data;
    } catch (error) {
      apiToast('레시피 상세 정보를 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createRecipe(payload) {
    try {
      const res = await axios.post('/agriseed/recipe-profiles/', payload);
      apiToast('레시피 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('레시피 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async updateRecipe(id, payload) {
    try {
      const res = await axios.put(`/agriseed/recipe-profiles/${id}/`, payload);
      apiToast('레시피 업데이트에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('레시피 업데이트에 실패했습니다.', 'error');
      throw error;
    }
  },

  async patchRecipe(id, payload) {
    try {
      const res = await axios.patch(`/agriseed/recipe-profiles/${id}/`, payload);
      apiToast('레시피 수정에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('레시피 수정에 실패했습니다.', 'error');
      throw error;
    }
  },

  async removeRecipe(id) {
    try {
      await axios.delete(`/agriseed/recipe-profiles/${id}/`);
      apiToast('레시피 삭제에 성공했습니다.', 'success');
    } catch (error) {
      apiToast('레시피 삭제에 실패했습니다.', 'error');
      throw error;
    }
  },

  async listComments(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/agriseed/recipe-comments/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('댓글 목록을 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createComment(payload) {
    try {
      const res = await axios.post('/agriseed/recipe-comments/', payload);
      apiToast('댓글 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('댓글 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async listVotes(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/agriseed/comment-votes/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('투표 목록을 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createVote(payload) {
    try {
      const res = await axios.post('/agriseed/comment-votes/', payload);
      apiToast('투표 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('투표 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async listPerformances(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/agriseed/recipe-performances/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('성과 목록을 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createPerformance(payload) {
    try {
      const res = await axios.post('/agriseed/recipe-performances/', payload);
      apiToast('성과 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('성과 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async listRatings(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/agriseed/recipe-ratings/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('별점 목록을 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createRating(payload) {
    try {
      const res = await axios.post('/agriseed/recipe-ratings/', payload);
      apiToast('별점 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('별점 생성에 실패했습니다.', 'error');
      throw error;
    }
  }
};

// by-variety 조회: 특정 품종 레시피 필터링 및 정렬
AgriseedService.listRecipesByVariety = async function(varietyId, params, options = {}) {
  try {
    const query = buildDjangoFilterParams(params)
    const res = await axios.get(`/agriseed/recipe-profiles/by-variety/${varietyId}/`, { params: query });
    const data = res.data;
    return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
  } catch (error) {
    apiToast('품종별 레시피 목록을 불러오는 데 실패했습니다.', 'error');
    throw error;
  }
};
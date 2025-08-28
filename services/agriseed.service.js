import axios from "axios";
import { showToast } from "./domUtils";

// Common usage: pass a `params` object to list methods for filtering and ordering, e.g. { status: 'active', ordering: '-id' }
export const AgriseedService = {
  async listDevices(params) {
    try {
      const res = await axios.get('/agriseed/devices/', { params });
      return res.data;
    } catch (error) {
      showToast('디바이스 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },

  async detailDevice(id) {
    try {
      const res = await axios.get(`/agriseed/devices/${id}/`);
      return res.data;
    } catch (error) {
      showToast('디바이스 상세 정보를 가져오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },

  async createDevice(payload) {
    try {
      const res = await axios.post('/agriseed/devices/', payload);
      showToast('디바이스가 생성되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('디바이스 생성에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async updateDevice(id, payload) {
    try {
      const res = await axios.put(`/agriseed/devices/${id}/`, payload);
      showToast('디바이스 정보가 업데이트되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('디바이스 업데이트에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async patchDevice(id, payload) {
    try {
      const res = await axios.patch(`/agriseed/devices/${id}/`, payload);
      showToast('디바이스 정보가 일부 수정되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('디바이스 부분 수정에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async removeDevice(id) {
    try {
      await axios.delete(`/agriseed/devices/${id}/`);
      showToast('디바이스가 삭제되었습니다.', 3000, 'success');
    } catch (error) {
      showToast('디바이스 삭제에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  async listActivities(params) {
    try {
      const res = await axios.get('/agriseed/activities/', { params });
      return res.data;
    } catch (error) {
      showToast('활동 목록 불러오기 실패', 3000, 'error');
      throw error;
    }
  },

  async detailActivity(id) {
    try {
      const res = await axios.get(`/agriseed/activities/${id}/`);
      return res.data;
    } catch (error) {
      showToast('활동 상세 조회 실패', 3000, 'error');
      throw error;
    }
  },

  async createActivity(payload) {
    try {
      const res = await axios.post('/agriseed/activities/', payload);
      showToast('활동 생성 성공', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('활동 생성 실패', 3000, 'error');
      throw error;
    }
  },

  async updateActivity(id, payload) {
    try {
      const res = await axios.put(`/agriseed/activities/${id}/`, payload);
      showToast('활동 업데이트 성공', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('활동 업데이트 실패', 3000, 'error');
      throw error;
    }
  },

  async patchActivity(id, payload) {
    try {
      const res = await axios.patch(`/agriseed/activities/${id}/`, payload);
      showToast('활동 수정 성공', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('활동 수정 실패', 3000, 'error');
      throw error;
    }
  },

  async removeActivity(id) {
    try {
      await axios.delete(`/agriseed/activities/${id}/`);
      showToast('활동 삭제 성공', 3000, 'success');
    } catch (error) {
      showToast('활동 삭제 실패', 3000, 'error');
      throw error;
    }
  },

  async listRecipes(params) {
    try {
      const res = await axios.get('/agriseed/recipe-profiles/', { params });
      return res.data;
    } catch (error) {
      showToast('레시피 목록 불러오기 실패', 3000, 'error');
      throw error;
    }
  },

  async detailRecipe(id) {
    try {
      const res = await axios.get(`/agriseed/recipe-profiles/${id}/`);
      return res.data;
    } catch (error) {
      showToast('레시피 상세 조회 실패', 3000, 'error');
      throw error;
    }
  },

  async createRecipe(payload) {
    try {
      const res = await axios.post('/agriseed/recipe-profiles/', payload);
      showToast('레시피 생성 성공', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('레시피 생성 실패', 3000, 'error');
      throw error;
    }
  },

  async updateRecipe(id, payload) {
    try {
      const res = await axios.put(`/agriseed/recipe-profiles/${id}/`, payload);
      showToast('레시피 업데이트 성공', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('레시피 업데이트 실패', 3000, 'error');
      throw error;
    }
  },

  async patchRecipe(id, payload) {
    try {
      const res = await axios.patch(`/agriseed/recipe-profiles/${id}/`, payload);
      showToast('레시피 수정 성공', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('레시피 수정 실패', 3000, 'error');
      throw error;
    }
  },

  async removeRecipe(id) {
    try {
      await axios.delete(`/agriseed/recipe-profiles/${id}/`);
      showToast('레시피 삭제 성공', 3000, 'success');
    } catch (error) {
      showToast('레시피 삭제 실패', 3000, 'error');
      throw error;
    }
  },

  async listComments(params) {
    try {
      const res = await axios.get('/agriseed/recipe-comments/', { params });
      return res.data;
    } catch (error) {
      showToast('댓글 목록 불러오기 실패', 3000, 'error');
      throw error;
    }
  },

  async createComment(payload) {
    try {
      const res = await axios.post('/agriseed/recipe-comments/', payload);
      showToast('댓글 생성 성공', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('댓글 생성 실패', 3000, 'error');
      throw error;
    }
  },

  async listVotes(params) {
    try {
      const res = await axios.get('/agriseed/comment-votes/', { params });
      return res.data;
    } catch (error) {
      showToast('투표 목록 불러오기 실패', 3000, 'error');
      throw error;
    }
  },

  async createVote(payload) {
    try {
      const res = await axios.post('/agriseed/comment-votes/', payload);
      showToast('투표 생성 성공', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('투표 생성 실패', 3000, 'error');
      throw error;
    }
  },

  async listPerformances(params) {
    try {
      const res = await axios.get('/agriseed/recipe-performances/', { params });
      return res.data;
    } catch (error) {
      showToast('성과 목록 불러오기 실패', 3000, 'error');
      throw error;
    }
  },

  async createPerformance(payload) {
    try {
      const res = await axios.post('/agriseed/recipe-performances/', payload);
      showToast('성과 생성 성공', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('성과 생성 실패', 3000, 'error');
      throw error;
    }
  },

  async listRatings(params) {
    try {
      const res = await axios.get('/agriseed/recipe-ratings/', { params });
      return res.data;
    } catch (error) {
      showToast('별점 목록 불러오기 실패', 3000, 'error');
      throw error;
    }
  },

  async createRating(payload) {
    try {
      const res = await axios.post('/agriseed/recipe-ratings/', payload);
      showToast('별점 생성 성공', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('별점 생성 실패', 3000, 'error');
      throw error;
    }
  }
};

// by-variety 조회: 특정 품종 레시피 필터링 및 정렬
AgriseedService.listRecipesByVariety = async function(varietyId, params) {
  try {
    const res = await axios.get(`/agriseed/recipe-profiles/by-variety/${varietyId}/`, { params });
    return res.data;
  } catch (error) {
    showToast('품종별 레시피 목록 불러오기 실패', 3000, 'error');
    throw error;
  }
};
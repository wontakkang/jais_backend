import api from '@/utils/apiClient'
import { showToast } from '@/utils/domUtils';
import { buildDjangoFilterParams } from '@/utils/django-filter.js';
import { normalizeData } from '@/utils/normalize.js';
import { normalizeList } from '@/utils/normalize.js';

// 표준 토스트 설정
const TOAST = {
  SUCCESS_DURATION: 3000,
  ERROR_DURATION: 5000
};

function apiToast(message, type = 'error') {
  const duration = type === 'success' ? TOAST.SUCCESS_DURATION : TOAST.ERROR_DURATION;
  showToast(message, duration, type);
}

// Common usage: pass a `params` object to list methods for filtering and ordering, e.g. { status: 'active', ordering: '-id' }
export const AgriseedService = {
  async listDevices(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/agriseed/devices/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('디바이스 목록을 불러오는 중 오류가 발생했습니다.', 'error');
      throw error;
    }
  },

  async detailDevice(id) {
    try {
      const res = await api.get(`/agriseed/devices/${id}/`);
      return res.data;
    } catch (error) {
      apiToast('디바이스 상세 정보를 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createDevice(payload) {
    try {
      const res = await api.post('/agriseed/devices/', payload);
      apiToast('디바이스 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('디바이스 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async updateDevice(id, payload) {
    try {
      const res = await api.put(`/agriseed/devices/${id}/`, payload);
      apiToast('디바이스 정보 업데이트에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('디바이스 업데이트에 실패했습니다.', 'error');
      throw error;
    }
  },

  async patchDevice(id, payload) {
    try {
      const res = await api.patch(`/agriseed/devices/${id}/`, payload);
      apiToast('디바이스 정보 부분 수정에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('디바이스 정보 부분 수정에 실패했습니다.', 'error');
      throw error;
    }
  },

  async removeDevice(id) {
    try {
      await api.delete(`/agriseed/devices/${id}/`);
      apiToast('디바이스 삭제에 성공했습니다.', 'success');
    } catch (error) {
      apiToast('디바이스 삭제에 실패했습니다.', 'error');
      throw error;
    }
  },

  async listActivities(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/agriseed/activities/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('활동 목록을 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async detailActivity(id) {
    try {
      const res = await api.get(`/agriseed/activities/${id}/`);
      return res.data;
    } catch (error) {
      apiToast('활동 상세 정보를 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createActivity(payload) {
    try {
      const res = await api.post('/agriseed/activities/', payload);
      apiToast('활동 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('활동 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async updateActivity(id, payload) {
    try {
      const res = await api.put(`/agriseed/activities/${id}/`, payload);
      apiToast('활동 업데이트에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('활동 업데이트에 실패했습니다.', 'error');
      throw error;
    }
  },

  async patchActivity(id, payload) {
    try {
      const res = await api.patch(`/agriseed/activities/${id}/`, payload);
      apiToast('활동 수정에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('활동 수정에 실패했습니다.', 'error');
      throw error;
    }
  },

  async removeActivity(id) {
    try {
      await api.delete(`/agriseed/activities/${id}/`);
      apiToast('활동 삭제에 성공했습니다.', 'success');
    } catch (error) {
      apiToast('활동 삭제에 실패했습니다.', 'error');
      throw error;
    }
  },

  async listRecipes(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/agriseed/recipe-profiles/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('레시피 목록을 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async detailRecipe(id) {
    try {
      const res = await api.get(`/agriseed/recipe-profiles/${id}/`);
      return res.data;
    } catch (error) {
      apiToast('레시피 상세 정보를 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createRecipe(payload) {
    try {
      const res = await api.post('/agriseed/recipe-profiles/', payload);
      apiToast('레시피 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('레시피 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async updateRecipe(id, payload) {
    try {
      const res = await api.put(`/agriseed/recipe-profiles/${id}/`, payload);
      apiToast('레시피 업데이트에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('레시피 업데이트에 실패했습니다.', 'error');
      throw error;
    }
  },

  async patchRecipe(id, payload) {
    try {
      const res = await api.patch(`/agriseed/recipe-profiles/${id}/`, payload);
      apiToast('레시피 수정에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('레시피 수정에 실패했습니다.', 'error');
      throw error;
    }
  },

  async removeRecipe(id) {
    try {
      await api.delete(`/agriseed/recipe-profiles/${id}/`);
      apiToast('레시피 삭제에 성공했습니다.', 'success');
    } catch (error) {
      apiToast('레시피 삭제에 실패했습니다.', 'error');
      throw error;
    }
  },

  // Recipe-steps (individual step) operations
  async createRecipeStep(payload) {
    try {
      const res = await api.post('/agriseed/recipe-steps/', payload);
      apiToast('생장 단계 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('생장 단계 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async patchRecipeStep(id, payload) {
    try {
      // 먼저 payload.item_values 중 control_item이 null이거나 없고 서버에 생성되지 않은 항목은
      // 개별 생성 요청을 보냅니다. 생성된 항목은 payload의 해당 인덱스를 대체합니다.
      if (payload && Array.isArray(payload.item_values)) {
        const creations = []
        payload.item_values = payload.item_values.map(iv => ({ ...iv }))
        for (let i = 0; i < payload.item_values.length; i++) {
          const iv = payload.item_values[i]
          const needsCreate = (iv.control_item == null) && (!iv.id || (typeof iv.id === 'number' && iv.id <= 0))
          if (needsCreate) {
            // POST 생성, 서버가 기본값을 채워 반환한다고 가정
            creations.push({ index: i, promise: api.post('/agriseed/recipe-item-values/', {
              set_value: iv.set_value,
              min_value: iv.min_value,
              max_value: iv.max_value,
              control_logic: iv.control_logic,
              priority: iv.priority
            }) })
          }
        }

        let createdObjects = []
        if (creations.length) {
          // 생성된 객체와 생성 인덱스를 추적
          const results = await Promise.all(creations.map(c => c.promise.then(res => res.data)))
          results.forEach((created, idx) => {
            const targetIndex = creations[idx].index
            // 생성된 객체로 기존 항목 교체(서버가 반환한 id/control_item 등 포함)
            payload.item_values[targetIndex] = created
          })
          createdObjects = results
        }

        try {
          const res = await api.patch(`/agriseed/recipe-steps/${id}/`, payload);
          apiToast('생장 단계 저장에 성공했습니다.', 'success');
          return res.data;
        } catch (err) {
          // PATCH 실패하면 앞서 생성한 recipe-item-values를 롤백(삭제)하여 orphan 방지
          if (createdObjects && createdObjects.length) {
            try {
              await Promise.all(createdObjects.map(co => api.delete(`/agriseed/recipe-item-values/${co.id}/`)));
              apiToast('수정 실패로 생성된 항목을 롤백했습니다.', 'error');
            } catch (delErr) {
              // 롤백 실패 시 로그만 남기고 원래 에러를 던짐
              console.error('롤백 중 일부 항목 삭제에 실패했습니다.', delErr);
              apiToast('롤백 중 일부 항목 삭제에 실패했습니다. 수동 확인이 필요합니다.', 'error');
            }
          }
          throw err
        }
      } else {
        const res = await api.patch(`/agriseed/recipe-steps/${id}/`, payload);
        apiToast('생장 단계 저장에 성공했습니다.', 'success');
        return res.data;
      }
    } catch (error) {
      apiToast('생장 단계 저장에 실패했습니다.', 'error');
      throw error;
    }
  },

  async detailRecipeStep(id) {
    try {
      const res = await api.get(`/agriseed/recipe-steps/${id}/`);
      return res.data;
    } catch (error) {
      apiToast('생장 단계 상세 정보를 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async removeRecipeStep(id) {
    try {
      await api.delete(`/agriseed/recipe-steps/${id}/`);
      apiToast('생장 단계 삭제에 성공했습니다.', 'success');
    } catch (error) {
      apiToast('생장 단계 삭제에 실패했습니다.', 'error');
      throw error;
    }
  },

  // Recipe item values CRUD (개별 항목 생성/조회/수정/삭제)
  async listRecipeItemValues(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/agriseed/recipe-item-values/', { params: query })
      const data = res.data
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle)
    } catch (error) {
      apiToast('레시피 항목값 목록을 불러오는 데 실패했습니다.', 'error')
      throw error
    }
  },

  // Control items 목록 (기존에 store에서 직접 axios 호출로 사용하던 엔드포인트를 서비스로 이동)
  async listControlItems(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/agriseed/control-items/', { params: query })
      const data = res.data
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle)
    } catch (error) {
      apiToast('제어 항목 목록을 불러오는 데 실패했습니다.', 'error')
      throw error
    }
  },

  async detailRecipeItemValue(id) {
    try {
      const res = await api.get(`/agriseed/recipe-item-values/${id}/`)
      return res.data
    } catch (error) {
      apiToast('레시피 항목값 상세 정보를 불러오는 데 실패했습니다.', 'error')
      throw error
    }
  },

  async createRecipeItemValue(payload) {
    try {
      const res = await api.post('/agriseed/recipe-item-values/', payload)
      apiToast('레시피 항목값 생성에 성공했습니다.', 'success')
      return res.data
    } catch (error) {
      apiToast('레시피 항목값 생성에 실패했습니다.', 'error')
      throw error
    }
  },

  async updateRecipeItemValue(id, payload) {
    try {
      const res = await api.put(`/agriseed/recipe-item-values/${id}/`, payload)
      apiToast('레시피 항목값 업데이트에 성공했습니다.', 'success')
      return res.data
    } catch (error) {
      apiToast('레시피 항목값 업데이트에 실패했습니다.', 'error')
      throw error
    }
  },

  async patchRecipeItemValue(id, payload) {
    try {
      const res = await api.patch(`/agriseed/recipe-item-values/${id}/`, payload)
      apiToast('레시피 항목값 수정에 성공했습니다.', 'success')
      return res.data
    } catch (error) {
      apiToast('레시피 항목값 수정에 실패했습니다.', 'error')
      throw error
    }
  },

  async removeRecipeItemValue(id) {
    try {
      await api.delete(`/agriseed/recipe-item-values/${id}/`)
      apiToast('레시피 항목값 삭제에 성공했습니다.', 'success')
    } catch (error) {
      apiToast('레시피 항목값 삭제에 실패했습니다.', 'error')
      throw error
    }
  },

  async listComments(params) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/agriseed/recipe-comments/', { params: query });
      const data = res.data;
      // 댓글은 클라이언트에서 배열 형태로 처리하므로 일관되게 배열을 반환하도록 보정
      return normalizeList(data);
    } catch (error) {
      apiToast('댓글 목록을 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createComment(payload) {
    try {
      const res = await api.post('/agriseed/recipe-comments/', payload);
      apiToast('댓글 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('댓글 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async updateComment(id, payload) {
    try {
      const res = await api.put(`/agriseed/recipe-comments/${id}/`, payload);
      apiToast('댓글이 수정되었습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('댓글 수정에 실패했습니다.', 'error');
      throw error;
    }
  },

  async removeComment(id) {
    try {
      await api.delete(`/agriseed/recipe-comments/${id}/`);
      apiToast('댓글이 삭제되었습니다.', 'success');
    } catch (error) {
      apiToast('댓글 삭제에 실패했습니다.', 'error');
      throw error;
    }
  },

  async listVotes(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/agriseed/comment-votes/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('투표 목록을 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createVote(payload) {
    try {
      const res = await api.post('/agriseed/comment-votes/', payload);
      apiToast('투표 생성에 성공했습니다.', 'success');
      return res.data;
    } catch (error) {
      apiToast('투표 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async removeVote(id) {
    try {
      await api.delete(`/agriseed/comment-votes/${id}/`);
      apiToast('투표 취소에 성공했습니다.', 'success');
    } catch (error) {
      apiToast('투표 취소에 실패했습니다.', 'error');
      throw error;
    }
  },

  async listPerformances(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/agriseed/recipe-performances/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('성과 목록을 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createPerformance(payload) {
    try {
      const res = await api.post('/agriseed/recipe-performances/', payload);
      return res.data;
    } catch (error) {
      apiToast('성과 생성에 실패했습니다.', 'error');
      throw error;
    }
  },

  async listRatings(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await api.get('/agriseed/recipe-ratings/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      apiToast('별점 목록을 불러오는 데 실패했습니다.', 'error');
      throw error;
    }
  },

  async createRating(payload) {
    try {
      const res = await api.post('/agriseed/recipe-ratings/', payload);
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
    const res = await api.get(`/agriseed/recipe-profiles/by-variety/${varietyId}/`, { params: query });
    const data = res.data;
    return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
  } catch (error) {
    apiToast('품종별 레시피 목록을 불러오는 데 실패했습니다.', 'error');
    throw error;
  }
};

// Varieties CRUD
AgriseedService.listVarieties = async function(params, options = {}) {
  try {
    const query = buildDjangoFilterParams(params)
    const res = await api.get('/agriseed/varieties/', { params: query });
    const data = res.data;
    return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
  } catch (error) {
    apiToast('품종 목록을 불러오는 데 실패했습니다.', 'error');
    throw error;
  }
};

AgriseedService.detailVariety = async function(id) {
  try {
    const res = await api.get(`/agriseed/varieties/${id}/`);
    return res.data;
  } catch (error) {
    apiToast('품종 상세 정보를 불러오는 데 실패했습니다.', 'error');
    throw error;
  }
};

AgriseedService.createVariety = async function(payload) {
  try {
    // payload가 FormData인 경우 multipart 전송을 위한 헤더 설정
    const isForm = (typeof FormData !== 'undefined') && (payload instanceof FormData)
    const config = isForm ? { headers: { 'Content-Type': 'multipart/form-data' } } : {}
    const res = await api.post('/agriseed/varieties/', payload, config);
    apiToast('품종 생성에 성공했습니다.', 'success');
    return res.data;
  } catch (error) {
    apiToast('품종 생성에 실패했습니다.', 'error');
    throw error;
  }
};

AgriseedService.updateVariety = async function(id, payload) {
  try {
    const res = await api.put(`/agriseed/varieties/${id}/`, payload);
    apiToast('품종 업데이트에 성공했습니다.', 'success');
    return res.data;
  } catch (error) {
    apiToast('품종 업데이트에 실패했습니다.', 'error');
    throw error;
  }
};

AgriseedService.patchVariety = async function(id, payload) {
  try {
    const res = await api.patch(`/agriseed/varieties/${id}/`, payload);
    apiToast('품종 정보 부분 수정에 성공했습니다.', 'success');
    return res.data;
  } catch (error) {
    apiToast('품종 정보 부분 수정에 실패했습니다.', 'error');
    throw error;
  }
};

AgriseedService.removeVariety = async function(id) {
  try {
    await api.delete(`/agriseed/varieties/${id}/`);
    apiToast('품종 삭제에 성공했습니다.', 'success');
  } catch (error) {
    apiToast('품종 삭제에 실패했습니다.', 'error');
    throw error;
  }
};

// Crops CRUD
AgriseedService.listCrops = async function(params, options = {}) {
  try {
    const query = buildDjangoFilterParams(params)
    const res = await api.get('/agriseed/crops/', { params: query })
    const data = res.data
    return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle)
  } catch (error) {
    apiToast('작물 목록을 불러오는 데 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.detailCrop = async function(id) {
  try {
    const res = await api.get(`/agriseed/crops/${id}/`)
    return res.data
  } catch (error) {
    apiToast('작물 상세 정보를 불러오는 데 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.createCrop = async function(payload) {
  try {
    const res = await api.post('/agriseed/crops/', payload)
    apiToast('작물 생성에 성공했습니다.', 'success')
    return res.data
  } catch (error) {
    apiToast('작물 생성에 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.updateCrop = async function(id, payload) {
  try {
    const res = await api.put(`/agriseed/crops/${id}/`, payload)
    apiToast('작물 업데이트에 성공했습니다.', 'success')
    return res.data
  } catch (error) {
    apiToast('작물 업데이트에 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.patchCrop = async function(id, payload) {
  try {
    const res = await api.patch(`/agriseed/crops/${id}/`, payload)
    apiToast('작물 정보 수정에 성공했습니다.', 'success')
    return res.data
  } catch (error) {
    apiToast('작물 정보 수정에 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.removeCrop = async function(id) {
  try {
    await api.delete(`/agriseed/crops/${id}/`)
    apiToast('작물 삭제에 성공했습니다.', 'success')
  } catch (error) {
    apiToast('작물 삭제에 실패했습니다.', 'error')
    throw error
  }
}

// Facilities CRUD
AgriseedService.listFacilities = async function(params, options = {}) {
  try {
    const query = buildDjangoFilterParams(params)
    const res = await api.get('/agriseed/facilities/', { params: query })
    const data = res.data
    return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle)
  } catch (error) {
    apiToast('시설 목록을 불러오는 데 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.detailFacility = async function(id) {
  try {
    const res = await api.get(`/agriseed/facilities/${id}/`)
    return res.data
  } catch (error) {
    apiToast('시설 상세 정보를 불러오는 데 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.createFacility = async function(payload) {
  try {
    const res = await api.post('/agriseed/facilities/', payload)
    apiToast('시설 생성에 성공했습니다.', 'success')
    return res.data
  } catch (error) {
    apiToast('시설 생성에 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.updateFacility = async function(id, payload) {
  try {
    const res = await api.put(`/agriseed/facilities/${id}/`, payload)
    apiToast('시설 업데이트에 성공했습니다.', 'success')
    return res.data
  } catch (error) {
    apiToast('시설 업데이트에 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.patchFacility = async function(id, payload) {
  try {
    const res = await api.patch(`/agriseed/facilities/${id}/`, payload)
    apiToast('시설 정보 부분 수정에 성공했습니다.', 'success')
    return res.data
  } catch (error) {
    apiToast('시설 정보 부분 수정에 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.removeFacility = async function(id) {
  try {
    await api.delete(`/agriseed/facilities/${id}/`)
    apiToast('시설 삭제에 성공했습니다.', 'success')
  } catch (error) {
    apiToast('시설 삭제에 실패했습니다.', 'error')
    throw error
  }
}

// Zones CRUD
AgriseedService.listZones = async function(params, options = {}) {
  try {
    const query = buildDjangoFilterParams(params)
    const res = await api.get('/agriseed/zones/', { params: query })
    const data = res.data
    return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle)
  } catch (error) {
    apiToast('구역 목록을 불러오는 데 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.detailZone = async function(id) {
  try {
    const res = await api.get(`/agriseed/zones/${id}/`)
    return res.data
  } catch (error) {
    apiToast('구역 상세 정보를 불러오는 데 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.createZone = async function(payload) {
  try {
    const res = await api.post('/agriseed/zones/', payload)
    apiToast('구역 생성에 성공했습니다.', 'success')
    return res.data
  } catch (error) {
    apiToast('구역 생성에 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.updateZone = async function(id, payload) {
  try {
    const res = await api.put(`/agriseed/zones/${id}/`, payload)
    apiToast('구역 업데이트에 성공했습니다.', 'success')
    return res.data
  } catch (error) {
    apiToast('구역 업데이트에 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.removeZone = async function(id) {
  try {
    await api.delete(`/agriseed/zones/${id}/`)
    apiToast('구역 삭제에 성공했습니다.', 'success')
  } catch (error) {
    apiToast('구역 삭제에 실패했습니다.', 'error')
    throw error
  }
}

// Control settings CRUD
AgriseedService.listControlSettings = async function(params, options = {}) {
  try {
    const query = buildDjangoFilterParams(params)
    const res = await api.get('/agriseed/control-settings/', { params: query })
    const data = res.data
    return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle)
  } catch (error) {
    apiToast('제어설정 목록을 불러오는 데 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.detailControlSetting = async function(id) {
  try {
    const res = await api.get(`/agriseed/control-settings/${id}/`)
    return res.data
  } catch (error) {
    apiToast('제어설정 상세 정보를 불러오는 데 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.createControlSetting = async function(payload) {
  try {
    const res = await api.post('/agriseed/control-settings/', payload)
    apiToast('제어설정 생성에 성공했습니다.', 'success')
    return res.data
  } catch (error) {
    apiToast('제어설정 생성에 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.updateControlSetting = async function(id, payload) {
  try {
    const res = await api.put(`/agriseed/control-settings/${id}/`, payload)
    apiToast('제어설정 업데이트에 성공했습니다.', 'success')
    return res.data
  } catch (error) {
    apiToast('제어설정 업데이트에 실패했습니다.', 'error')
    throw error
  }
}

AgriseedService.removeControlSetting = async function(id) {
  try {
    await api.delete(`/agriseed/control-settings/${id}/`)
    apiToast('제어설정 삭제에 성공했습니다.', 'success')
  } catch (error) {
    apiToast('제어설정 삭제에 실패했습니다.', 'error')
    throw error
  }
}
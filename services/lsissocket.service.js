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

// Common usage: pass a `params` object to list methods for filtering and ordering, e.g. { config__id: 1, ordering: '-updated_at' }
export const LSISsocketService = {
  // Client Configs
  async listClientConfigs(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/LSISsocket/client-configs/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('클라이언트 설정 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },
  async detailClientConfig(id) {
    try {
      const res = await axios.get(`/LSISsocket/client-configs/${id}/`);
      return res.data;
    } catch (error) {
      showToast('클라이언트 설정 상세정보를 가져오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },
  async createClientConfig(payload) {
    try {
      const res = await axios.post('/LSISsocket/client-configs/', payload);
      showToast('클라이언트 설정이 생성되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('클라이언트 설정 생성에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async updateClientConfig(id, payload) {
    try {
      const res = await axios.put(`/LSISsocket/client-configs/${id}/`, payload);
      showToast('클라이언트 설정이 업데이트되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('클라이언트 설정 업데이트에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async patchClientConfig(id, payload) {
    try {
      const res = await axios.patch(`/LSISsocket/client-configs/${id}/`, payload);
      showToast('클라이언트 설정이 패치되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('클라이언트 설정 패치에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async removeClientConfig(id) {
    try {
      await axios.delete(`/LSISsocket/client-configs/${id}/`);
      showToast('클라이언트 설정이 삭제되었습니다.', 3000, 'success');
    } catch (error) {
      showToast('클라이언트 설정 삭제에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  // Client Status
  async listClientStatus(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/LSISsocket/client-status/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('클라이언트 상태 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },
  async detailClientStatus(id) {
    try {
      const res = await axios.get(`/LSISsocket/client-status/${id}/`);
      return res.data;
    } catch (error) {
      showToast('클라이언트 상태 상세정보를 가져오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },

  // Client Logs
  async listClientLogs(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/LSISsocket/client-logs/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('클라이언트 로그 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },
  async detailClientLog(id) {
    try {
      const res = await axios.get(`/LSISsocket/client-logs/${id}/`);
      return res.data;
    } catch (error) {
      showToast('클라이언트 로그 상세정보를 가져오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },

  // Sensor Node Configs
  async listSensorNodeConfigs(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/LSISsocket/sensor-node-configs/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('센서 노드 설정 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },
  async detailSensorNodeConfig(id) {
    try {
      const res = await axios.get(`/LSISsocket/sensor-node-configs/${id}/`);
      return res.data;
    } catch (error) {
      showToast('센서 노드 설정 상세정보를 가져오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },
  async createSensorNodeConfig(payload) {
    try {
      const res = await axios.post('/LSISsocket/sensor-node-configs/', payload);
      showToast('센서 노드 설정이 생성되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('센서 노드 설정 생성에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async updateSensorNodeConfig(id, payload) {
    try {
      const res = await axios.put(`/LSISsocket/sensor-node-configs/${id}/`, payload);
      showToast('센서 노드 설정이 업데이트되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('센서 노드 설정 업데이트에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async patchSensorNodeConfig(id, payload) {
    try {
      const res = await axios.patch(`/LSISsocket/sensor-node-configs/${id}/`, payload);
      showToast('센서 노드 설정이 패치되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('센서 노드 설정 패치에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async removeSensorNodeConfig(id) {
    try {
      await axios.delete(`/LSISsocket/sensor-node-configs/${id}/`);
      showToast('센서 노드 설정이 삭제되었습니다.', 3000, 'success');
    } catch (error) {
      showToast('센서 노드 설정 삭제에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  // Control Node Configs
  async listControlNodeConfigs(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/LSISsocket/control-node-configs/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('제어 노드 설정 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },
  async detailControlNodeConfig(id) {
    try {
      const res = await axios.get(`/LSISsocket/control-node-configs/${id}/`);
      return res.data;
    } catch (error) {
      showToast('제어 노드 설정 상세정보를 가져오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },
  async createControlNodeConfig(payload) {
    try {
      const res = await axios.post('/LSISsocket/control-node-configs/', payload);
      showToast('제어 노드 설정이 생성되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('제어 노드 설정 생성에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async updateControlNodeConfig(id, payload) {
    try {
      const res = await axios.put(`/LSISsocket/control-node-configs/${id}/`, payload);
      showToast('제어 노드 설정이 업데이트되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('제어 노드 설정 업데이트에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async patchControlNodeConfig(id, payload) {
    try {
      const res = await axios.patch(`/LSISsocket/control-node-configs/${id}/`, payload);
      showToast('제어 노드 설정이 패치되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('제어 노드 설정 패치에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async removeControlNodeConfig(id) {
    try {
      await axios.delete(`/LSISsocket/control-node-configs/${id}/`);
      showToast('제어 노드 설정이 삭제되었습니다.', 3000, 'success');
    } catch (error) {
      showToast('제어 노드 설정 삭제에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  // Client Commands
  async listClientCommands(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/LSISsocket/client-commands/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('클라이언트 명령 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },
  async detailClientCommand(id) {
    try {
      const res = await axios.get(`/LSISsocket/client-commands/${id}/`);
      return res.data;
    } catch (error) {
      showToast('클라이언트 명령 상세정보를 가져오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },
  async createClientCommand(payload) {
    try {
      const res = await axios.post('/LSISsocket/client-commands/', payload);
      showToast('클라이언트 명령이 생성되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('클라이언트 명령 생성에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async updateClientCommand(id, payload) {
    try {
      const res = await axios.put(`/LSISsocket/client-commands/${id}/`, payload);
      showToast('클라이언트 명령이 업데이트되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('클라이언트 명령 업데이트에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async patchClientCommand(id, payload) {
    try {
      const res = await axios.patch(`/LSISsocket/client-commands/${id}/`, payload);
      showToast('클라이언트 명령이 패치되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('클라이언트 명령 패치에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async removeClientCommand(id) {
    try {
      await axios.delete(`/LSISsocket/client-commands/${id}/`);
      showToast('클라이언트 명령이 삭제되었습니다.', 3000, 'success');
    } catch (error) {
      showToast('클라이언트 명령 삭제에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  // Adapters
  async listAdapters(params, options = {}) {
    try {
      const query = buildDjangoFilterParams(params)
      const res = await axios.get('/LSISsocket/adapters/', { params: query });
      const data = res.data;
      return normalizeData(data, options.responseType || options.type || 'original', options.wrapSingle);
    } catch (error) {
      showToast('어댑터 목록을 불러오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },
  async detailAdapter(id) {
    try {
      const res = await axios.get(`/LSISsocket/adapters/${id}/`);
      return res.data;
    } catch (error) {
      showToast('어댑터 상세정보를 가져오는 중 오류가 발생했습니다.', 3000, 'error');
      throw error;
    }
  },
  async createAdapter(payload) {
    try {
      const res = await axios.post('/LSISsocket/adapters/', payload);
      showToast('어댑터가 생성되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('어댑터 생성에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async updateAdapter(id, payload) {
    try {
      const res = await axios.put(`/LSISsocket/adapters/${id}/`, payload);
      showToast('어댑터가 업데이트되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('어댑터 업데이트에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async patchAdapter(id, payload) {
    try {
      const res = await axios.patch(`/LSISsocket/adapters/${id}/`, payload);
      showToast('어댑터가 패치되었습니다.', 3000, 'success');
      return res.data;
    } catch (error) {
      showToast('어댑터 패치에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async removeAdapter(id) {
    try {
      await axios.delete(`/LSISsocket/adapters/${id}/`);
      showToast('어댑터가 삭제되었습니다.', 3000, 'success');
    } catch (error) {
      showToast('어댑터 삭제에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },

  // LSIS CPU Commands
  async initReset(params) {
    try {
      const qp = buildDjangoFilterParams(params);
      await axios.post('/LSISsocket/cpu/init-reset/', null, { params: qp });
      showToast('CPU 초기화 리셋 명령이 전송되었습니다.', 3000, 'success');
    } catch (error) {
      showToast('CPU 초기화 리셋 명령 전송에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async stop(params) {
    try {
      const qp = buildDjangoFilterParams(params);
      await axios.post('/LSISsocket/cpu/stop/', null, { params: qp });
      showToast('CPU 정지 명령이 전송되었습니다.', 3000, 'success');
    } catch (error) {
      showToast('CPU 정지 명령 전송에 실패했습니다.', 3000, 'error');
      throw error;
    }
  },
  async run(params) {
    try {
      const qp = buildDjangoFilterParams(params);
      await axios.post('/LSISsocket/cpu/run/', null, { params: qp });
      showToast('CPU 실행 명령이 전송되었습니다.', 3000, 'success');
    } catch (error) {
      showToast('CPU 실행 명령 전송에 실패했습니다.', 3000, 'error');
      throw error;
    }
  }
};
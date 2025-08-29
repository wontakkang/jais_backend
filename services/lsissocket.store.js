import { defineStore } from 'pinia';
import { LSISsocketService } from './lsissocket.service';
import { showToast } from '@/utils/domUtils';

// Common params: filtering and ordering via `params`, e.g. { config__id: 1, ordering: '-updated_at' }
export const useLSISsocketStore = defineStore('lsissocket', {
  state: () => ({
    clientConfigs: [],
    clientStatus: [],
    clientLogs: [],
    sensorNodeConfigs: [],
    controlNodeConfigs: [],
    clientCommands: [],
    adapters: []
  }),
  actions: {
    // Client Configs CRUD
    async fetchClientConfigs(params) {
      this.clientConfigs = await LSISsocketService.listClientConfigs(params);
    },
    async createClientConfig(data) {
      const c = await LSISsocketService.createClientConfig(data);
      this.clientConfigs.push(c);
      return c;
    },
    async updateClientConfig(id, data) {
      const u = await LSISsocketService.updateClientConfig(id, data);
      const idx = this.clientConfigs.findIndex(x => x.id === id);
      if (idx !== -1) this.clientConfigs.splice(idx, 1, u);
      return u;
    },
    async deleteClientConfig(id) {
      await LSISsocketService.removeClientConfig(id);
      this.clientConfigs = this.clientConfigs.filter(x => x.id !== id);
    },

    // Client Status
    async fetchClientStatus(params) {
      this.clientStatus = await LSISsocketService.listClientStatus(params);
    },
    async getClientStatus(id) {
      return await LSISsocketService.detailClientStatus(id);
    },

    // Client Logs
    async fetchClientLogs(params) {
      this.clientLogs = await LSISsocketService.listClientLogs(params);
    },
    async getClientLog(id) {
      return await LSISsocketService.detailClientLog(id);
    },

    // Sensor Node Configs CRUD
    async fetchSensorNodeConfigs(params) {
      this.sensorNodeConfigs = await LSISsocketService.listSensorNodeConfigs(params);
    },
    async createSensorNodeConfig(data) {
      const s = await LSISsocketService.createSensorNodeConfig(data);
      this.sensorNodeConfigs.push(s);
      return s;
    },
    async updateSensorNodeConfig(id, data) {
      const u = await LSISsocketService.updateSensorNodeConfig(id, data);
      const idx = this.sensorNodeConfigs.findIndex(x => x.id === id);
      if (idx !== -1) this.sensorNodeConfigs.splice(idx, 1, u);
      return u;
    },
    async deleteSensorNodeConfig(id) {
      await LSISsocketService.removeSensorNodeConfig(id);
      this.sensorNodeConfigs = this.sensorNodeConfigs.filter(x => x.id !== id);
    },

    // Control Node Configs CRUD
    async fetchControlNodeConfigs(params) {
      this.controlNodeConfigs = await LSISsocketService.listControlNodeConfigs(params);
    },
    async createControlNodeConfig(data) {
      const c = await LSISsocketService.createControlNodeConfig(data);
      this.controlNodeConfigs.push(c);
      return c;
    },
    async updateControlNodeConfig(id, data) {
      const u = await LSISsocketService.updateControlNodeConfig(id, data);
      const idx = this.controlNodeConfigs.findIndex(x => x.id === id);
      if (idx !== -1) this.controlNodeConfigs.splice(idx, 1, u);
      return u;
    },
    async deleteControlNodeConfig(id) {
      await LSISsocketService.removeControlNodeConfig(id);
      this.controlNodeConfigs = this.controlNodeConfigs.filter(x => x.id !== id);
    },

    // Client Commands CRUD
    async fetchClientCommands(params) {
      this.clientCommands = await LSISsocketService.listClientCommands(params);
    },
    async createClientCommand(data) {
      const c = await LSISsocketService.createClientCommand(data);
      this.clientCommands.push(c);
      return c;
    },
    async updateClientCommand(id, data) {
      const u = await LSISsocketService.updateClientCommand(id, data);
      const idx = this.clientCommands.findIndex(x => x.id === id);
      if (idx !== -1) this.clientCommands.splice(idx, 1, u);
      return u;
    },
    async deleteClientCommand(id) {
      await LSISsocketService.removeClientCommand(id);
      this.clientCommands = this.clientCommands.filter(x => x.id !== id);
    },

    // Adapters CRUD
    async fetchAdapters(params) {
      this.adapters = await LSISsocketService.listAdapters(params);
    },
    async createAdapter(data) {
      const a = await LSISsocketService.createAdapter(data);
      this.adapters.push(a);
      return a;
    },
    async updateAdapter(id, data) {
      const u = await LSISsocketService.updateAdapter(id, data);
      const idx = this.adapters.findIndex(x => x.id === id);
      if (idx !== -1) this.adapters.splice(idx, 1, u);
      return u;
    },
    async deleteAdapter(id) {
      await LSISsocketService.removeAdapter(id);
      this.adapters = this.adapters.filter(x => x.id !== id);
    },

    // LSIS CPU commands
    async initReset(params) {
      return await LSISsocketService.initReset(params);
    },
    async stopCPU(params) {
      return await LSISsocketService.stop(params);
    },
    async runCPU(params) {
      return await LSISsocketService.run(params);
    }
  }
});
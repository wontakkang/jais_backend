// utils/domUtils.js
import axios from 'axios';

export function setupNotificationAndAccountToggles(notificationBtnId, notificationPopupId, accountBtnId, accountMenuId) {
  const notificationBtn = document.getElementById(notificationBtnId);
  const notificationPopup = document.getElementById(notificationPopupId);
  const accountBtn = document.getElementById(accountBtnId);
  const accountMenu = document.getElementById(accountMenuId);

  // 알림 팝업 토글
  if (notificationBtn && notificationPopup && accountMenu) {
    notificationBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      notificationPopup.classList.toggle("hidden");
      accountMenu.classList.add("hidden");
    });
  }

  // 계정 메뉴 토글
  if (accountBtn && accountMenu && notificationPopup) {
    accountBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      accountMenu.classList.toggle("hidden");
      notificationPopup.classList.add("hidden");
    });
  }

  // 외부 클릭시 팝업 닫기
  document.addEventListener("click", function (e) {
    if (notificationBtn && notificationPopup && !notificationBtn.contains(e.target) && !notificationPopup.contains(e.target)) {
      notificationPopup.classList.add("hidden");
    }
    if (accountBtn && accountMenu && !accountBtn.contains(e.target) && !accountMenu.contains(e.target)) {
      accountMenu.classList.add("hidden");
    }
  });
}

export function showToast(message, duration = 3000, type = 'info') {
  const toast = document.createElement('div');
  toast.textContent = message;
  toast.style.position = 'fixed';
  toast.style.bottom = '20px';
  toast.style.left = '50%';
  toast.style.transform = 'translateX(-50%)';
  toast.style.color = 'white';
  toast.style.padding = '10px 20px';
  toast.style.borderRadius = '5px';
  toast.style.zIndex = '1000';

  // style by type
  let bgColor;
  switch(type) {
    case 'success': bgColor = 'rgba(40, 167, 69, 0.9)'; break;
    case 'error': bgColor = 'rgba(220, 53, 69, 0.9)'; break;
    case 'warning': bgColor = 'rgba(255, 193, 7, 0.9)'; break;
    default: bgColor = 'rgba(0, 0, 0, 0.8)';
  }
  toast.style.backgroundColor = bgColor;

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, duration);
}

export async function saveOrUpdateResource(store, url, formData, resourceName, name_key = 'name') {
  try {
    let response;
    if (formData.id) {
      response = await axios.put(`${url}${formData.id}/`, formData);
      showToast(`${response.data[name_key]}가 성공적으로 업데이트되었습니다.`, 3000, 'success');
      // Update the existing item in the array
      const index = store[resourceName]?.findIndex(item => item.id === formData.id);
      if (index !== undefined && index !== -1) {
        store[resourceName].splice(index, 1, response.data);
      }
    } else {
      delete formData.id;
      delete formData.data;
      response = await axios.post(url, formData);
      showToast(`${response.data[name_key]}가 성공적으로 생성되었습니다.`, 3000, 'success');
      // Push the new item to the array
      if (store[resourceName]) {
        store[resourceName].push(response.data);
      }
    }
    return response.data;
  } catch (error) {
    let ToastMessage = '';
    if (error.response?.data) {
      for (const key in error.response.data) {
        ToastMessage = `${key}: (${error.response.data[key]})`;
      }
    } else {
      ToastMessage = `${resourceName || '리소스'} 저장/수정 중 오류가 발생했습니다.`;
    }
    showToast(ToastMessage, 3000, 'error');
    throw error;
  }
}

/**
 * 기존 groups와 새로운 groups를 비교하여 변경 요약 문자열을 반환
 * @param {Array} oldGroups 기존 groups
 * @param {Array} newGroups 저장하려는 groups
 * @returns {string} 변경 요약
 */
export function summarizeGroupsDiff(oldGroups, newGroups) {
  let summary = [];

  // 그룹 ID 목록 추출
  const oldGroupMap = Object.fromEntries((oldGroups || []).map(g => [g.group_id, g]));
  const newGroupMap = Object.fromEntries((newGroups || []).map(g => [g.group_id, g]));
  const allGroupIds = Array.from(new Set([
    ...Object.keys(oldGroupMap),
    ...Object.keys(newGroupMap)
  ]));

  // 그룹 추가/삭제/변경
  allGroupIds.forEach(groupId => {
    const oldGroup = oldGroupMap[groupId];
    const newGroup = newGroupMap[groupId];
    if (!oldGroup) {
      summary.push(`그룹 추가: ${groupId}`);
      if (newGroup.variables && newGroup.variables.length) {
        newGroup.variables.forEach(v => {
          summary.push(`  └ 변수 추가: ${v.name} (타입: ${v.data_type}, 스케일: ${v.scale})`);
        });
      }
      return;
    }
    if (!newGroup) {
      summary.push(`그룹 삭제: ${groupId}`);
      if (oldGroup.variables && oldGroup.variables.length) {
        oldGroup.variables.forEach(v => {
          summary.push(`  └ 변수 삭제: ${v.name} (타입: ${v.data_type}, 스케일: ${v.scale})`);
        });
      }
      return;
    }
    // 그룹 속성 변경
    if (oldGroup.name !== newGroup.name) {
      summary.push(`그룹 ${groupId} 이름 변경: ${oldGroup.name} → ${newGroup.name}`);
    }
    if (oldGroup.size_byte !== newGroup.size_byte) {
      summary.push(`그룹 ${groupId} 크기 변경: ${oldGroup.size_byte} → ${newGroup.size_byte}`);
    }
    if (oldGroup.start_device !== newGroup.start_device) {
      summary.push(`그룹 ${groupId} 시작 디바이스 변경: ${oldGroup.start_device} → ${newGroup.start_device}`);
    }
    if (oldGroup.start_address !== newGroup.start_address) {
      summary.push(`그룹 ${groupId} 시작 주소 변경: ${oldGroup.start_address} → ${newGroup.start_address}`);
    }
    // 변수 비교
    const oldVarMap = Object.fromEntries((oldGroup.variables || []).map(v => [v.name, v]));
    const newVarMap = Object.fromEntries((newGroup.variables || []).map(v => [v.name, v]));
    const allVarNames = Array.from(new Set([
      ...Object.keys(oldVarMap),
      ...Object.keys(newVarMap)
    ]));
    allVarNames.forEach(varName => {
      const oldVar = oldVarMap[varName];
      const newVar = newVarMap[varName];
      if (!oldVar) {
        summary.push(`  └ 변수 추가: ${varName} (타입: ${newVar.data_type}, 스케일: ${newVar.scale})`);
        return;
      }
      if (!newVar) {
        summary.push(`  └ 변수 삭제: ${varName} (타입: ${oldVar.data_type}, 스케일: ${oldVar.scale})`);
        return;
      }
      // 변수 속성 변경
      if (oldVar.data_type !== newVar.data_type) {
        summary.push(`  └ 변수 ${varName} 데이터 타입 변경: ${oldVar.data_type} → ${newVar.data_type}`);
      }
      if (oldVar.scale !== newVar.scale) {
        summary.push(`  └ 변수 ${varName} 스케일 변경: ${oldVar.scale} → ${newVar.scale}`);
      }
      if (oldVar.unit !== newVar.unit) {
        summary.push(`  └ 변수 ${varName} 단위 변경: ${oldVar.unit} → ${newVar.unit}`);
      }
      if (oldVar.address !== newVar.address) {
        summary.push(`  └ 변수 ${varName} 주소 변경: ${oldVar.address} → ${newVar.address}`);
      }
      if (oldVar.device !== newVar.device) {
        summary.push(`  └ 변수 ${varName} 디바이스 변경: ${oldVar.device} → ${newVar.device}`);
      }
    });
  });

  return summary.length ? summary.join('\n') : '변경사항 없음';
}
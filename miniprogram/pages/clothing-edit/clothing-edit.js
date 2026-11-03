const api = require('../../utils/api');
const { TAG_GROUPS } = require('../../utils/constants');
const app = getApp();

function makeTagGroups(tags) {
  return TAG_GROUPS.map(group => ({
    key: group.key,
    label: group.label,
    options: group.options.map(name => ({ name, selected: (tags[group.key] || []).indexOf(name) >= 0 })),
  }));
}

function hasSavedTags(item, tags) {
  if (!item) return false;
  const keys = ['season_tags', 'occasion_tags', 'style_tags', 'material_tags'];
  return keys.every(key => {
    if (!Array.isArray(item[key])) return false;
    const expected = (tags[key] || []).slice().sort();
    const actual = item[key].slice().sort();
    return expected.length === actual.length && expected.every((tag, index) => tag === actual[index]);
  });
}

function assertTagsSaved(item, tags) {
  if (!hasSavedTags(item, tags)) {
    const error = new Error('标签未保存');
    error.code = 'TAGS_NOT_SAVED';
    throw error;
  }
  return item;
}

function showSaveError(error, fallback) {
  if (error && error.code === 'TAGS_NOT_SAVED') {
    wx.showModal({
      title: '标签未保存',
      content: '后端可能还在运行旧版本。请重启后端，再编辑并保存这件衣物。',
      showCancel: false,
    });
    return;
  }
  wx.showToast({ title: fallback, icon: 'none', duration: 2500 });
}

Page({
  data: {
    id: 0,              // 编辑模式 >0,新增模式 =0
    category: '', color: '', remark: '',
    tags: { season_tags: [], occasion_tags: [], style_tags: [], material_tags: [] },
    tagGroups: makeTagGroups({}),
    photoPath: '',      // 本地临时路径(新选图后才有)
    photoFull: '',      // 展示用绝对路径(已有图=baseUrl+url;新选=本地路径)
    pendingUploadId: 0,
    pendingUploadMessage: '已添加',
    uploadFailed: false,
    saving: false, uploading: false,
  },

  onLoad(query) {
    if (query && query.id) {
      this.setData({ id: Number(query.id) });
      wx.setNavigationBarTitle({ title: '编辑衣物' });
      this._loadItem(this.data.id);
    }
  },

  _loadItem(id) {
    api.clothing.get(id)
      .then(item => {
        if (!item) return;
        this.setData({
          category: item.category || '',
          color: item.color || '',
          remark: item.remark || '',
          tags: {
            season_tags: item.season_tags || [],
            occasion_tags: item.occasion_tags || [],
            style_tags: item.style_tags || [],
            material_tags: item.material_tags || [],
          },
          tagGroups: makeTagGroups(item),
          photoFull: item.photo_url ? app.globalData.baseUrl + item.photo_url : '',
        });
      })
      .catch(() => wx.showToast({ title: '加载失败', icon: 'none' }));
  },

  onCategory(e) { this.setData({ category: e.detail.value }); },
  onColor(e) { this.setData({ color: e.detail.value }); },
  onRemark(e) { this.setData({ remark: e.detail.value }); },

  toggleTag(e) {
    const groupKey = e.currentTarget.dataset.group;
    const tagName = e.currentTarget.dataset.tag;
    const selected = (this.data.tags[groupKey] || []).slice();
    const index = selected.indexOf(tagName);
    if (index >= 0) selected.splice(index, 1);
    else selected.push(tagName);
    const tags = Object.assign({}, this.data.tags);
    tags[groupKey] = selected;
    this.setData({ tags, tagGroups: makeTagGroups(tags) });
  },

  // 选图:优先 wx.chooseMedia(新),回退 wx.chooseImage(老基础库)
  choosePhoto() {
    if (this.data.uploading) return;
    const pick = (path) => this.setData({ photoPath: path, photoFull: path });
    if (wx.chooseMedia) {
      wx.chooseMedia({
        count: 1, mediaType: ['image'], sourceType: ['album', 'camera'], sizeType: ['compressed'],
        success: r => pick(r.tempFiles[0].tempFilePath),
      });
    } else {
      wx.chooseImage({ count: 1, sizeType: ['compressed'], success: r => pick(r.tempFilePaths[0]) });
    }
  },

  save() {
    const { id, category, color, remark, tags, photoPath, photoFull, saving, uploading } = this.data;
    if (saving || uploading) return;
    if (!category) { wx.showToast({ title: '请选择分类', icon: 'none' }); return; }
    // 没图(无论新增或编辑)就必须有颜色:有 photoFull=已有图或新选图
    if (!photoFull && !color) { wx.showToast({ title: '请选颜色或上传图片', icon: 'none' }); return; }
    this.setData({ saving: true });

    if (id) {
      // 编辑:先更新文本字段,再传新图(若选了)
      api.clothing.update(id, Object.assign({ category, color: color || null, remark }, tags))
        .then(item => assertTagsSaved(item, tags))
        .then(() => {
          if (!photoPath) { this._done('已更新'); return; }
          this.setData({ saving: false });
          this._uploadPhoto(id, '已更新');
        })
        .catch(error => {
          showSaveError(error, '更新失败');
          this.setData({ saving: false });
        });
    } else {
      // 新增
      api.clothing.create(Object.assign({ category, color: color || null, remark }, tags))
        .then(item => assertTagsSaved(item, tags))
        .then(item => {
          if (!photoPath) { this._done('已添加'); return; }
          this.setData({ saving: false });
          this._uploadPhoto(item.id, '已添加');
        })
        .catch(error => {
          showSaveError(error, '保存失败');
          this.setData({ saving: false });
        });
    }
  },

  _uploadPhoto(itemId, successMessage) {
    this.setData({
      uploading: true,
      uploadFailed: false,
      pendingUploadId: itemId,
      pendingUploadMessage: successMessage,
    });
    api.clothing.uploadPhoto(itemId, this.data.photoPath)
      .then(() => this._done(successMessage))
      .catch(() => {
        this.setData({ uploading: false, uploadFailed: true });
        wx.showToast({ title: '图片上传失败，可重试', icon: 'none', duration: 2500 });
      });
  },

  retryPhotoUpload() {
    const { pendingUploadId, pendingUploadMessage, photoPath, uploading } = this.data;
    if (uploading || !pendingUploadId || !photoPath) return;
    this._uploadPhoto(pendingUploadId, pendingUploadMessage);
  },

  continueWithoutPhoto() {
    this._done('衣物已保存');
  },

  remove() {
    const { id } = this.data;
    if (!id) return;
    wx.showModal({
      title: '删除衣物', content: '确定删除这件衣物?删除后不可恢复。',
      confirmText: '删除', confirmColor: '#d93025',
      success: r => {
        if (!r.confirm) return;
        api.clothing.remove(id)
          .then(() => { wx.showToast({ title: '已删除', icon: 'success' }); setTimeout(() => wx.navigateBack(), 500); })
          .catch(() => wx.showToast({ title: '删除失败', icon: 'none' }));
      },
    });
  },

  _done(msg) {
    wx.showToast({ title: msg, icon: 'success' });
    setTimeout(() => wx.navigateBack(), 600);
    this.setData({ saving: false, uploading: false, uploadFailed: false });
  },
});

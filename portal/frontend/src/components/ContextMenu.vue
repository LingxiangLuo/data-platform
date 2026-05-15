<template>
  <Teleport to="body">
    <Transition name="menu-fade">
      <div v-if="visible" class="context-menu-overlay" @click="onOverlayClick">
        <div
          ref="menuRef"
          class="context-menu"
          :style="menuStyle"
          @click.stop
        >
          <MenuList :items="items" @select="onSelect" />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'

export interface MenuItem {
  key?: string
  label?: string
  icon?: string
  disabled?: boolean
  danger?: boolean
  children?: MenuItem[]
  divider?: boolean
}

const props = defineProps<{
  visible: boolean
  x: number
  y: number
  items: MenuItem[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'select', key: string): void
}>()

const menuRef = ref<HTMLElement>()

const menuStyle = computed(() => {
  let left = props.x
  let top = props.y
  return {
    left: `${left}px`,
    top: `${top}px`,
  }
})

function close() {
  emit('update:visible', false)
}

function onOverlayClick() {
  close()
}

function onSelect(key: string) {
  emit('select', key)
  close()
}

watch(() => props.visible, (v) => {
  if (v) {
    nextTick(() => {
      const handler = (e: MouseEvent) => {
        if (!menuRef.value?.contains(e.target as Node)) {
          close()
          document.removeEventListener('mousedown', handler)
        }
      }
      document.addEventListener('mousedown', handler)
    })
  }
})
</script>

<script lang="ts">
// 子菜单列表（递归组件）
import { h, defineComponent } from 'vue'

const MenuList: any = defineComponent({
  name: 'MenuList',
  props: {
    items: { type: Array as () => MenuItem[], required: true },
    nested: { type: Boolean, default: false },
  },
  emits: ['select'],
  setup(props: { items: MenuItem[]; nested: boolean }, { emit }: { emit: (e: 'select', key: string) => void }) {
    const activeKey = ref<string | null>(null)
    let hideTimer: any = null

    function onItemClick(item: MenuItem) {
      if (item.disabled || item.children?.length) return
      emit('select', item.key!)
    }

    function onMouseEnter(item: MenuItem) {
      if (hideTimer) {
        clearTimeout(hideTimer)
        hideTimer = null
      }
      if (item.children?.length) {
        activeKey.value = item.key ?? null
      } else {
        activeKey.value = null
      }
    }

    function onMouseLeave() {
      hideTimer = setTimeout(() => {
        activeKey.value = null
      }, 300)
    }

    return (): any => h('ul', { class: ['menu-list', { 'menu-nested': props.nested }] },
      props.items.map((item): any => {
        if (item.divider) {
          return h('li', { class: 'menu-divider' })
        }
        const hasChildren = !!item.children?.length
        const isActive = activeKey.value === item.key
        return h('li', {
          class: [
            'menu-item',
            {
              'menu-disabled': item.disabled,
              'menu-danger': item.danger,
              'menu-active': isActive,
              'menu-has-children': hasChildren,
            },
          ],
          onClick: () => onItemClick(item),
          onMouseenter: () => onMouseEnter(item),
          onMouseleave: onMouseLeave,
        }, [
          h('span', { class: 'menu-label' }, item.label),
          hasChildren && h('span', { class: 'menu-arrow' }, '▶'),
          hasChildren && isActive && h('div', {
            class: 'menu-submenu',
            onMouseenter: () => {
              if (hideTimer) { clearTimeout(hideTimer); hideTimer = null }
              activeKey.value = item.key ?? null
            },
            onMouseleave: onMouseLeave,
          }, [
            h(MenuList, {
              items: item.children!,
              nested: true,
              onSelect: (key: string) => emit('select', key),
            }),
          ]),
        ])
      })
    )
  },
})
</script>

<style scoped>
.context-menu-overlay {
  position: fixed;
  inset: 0;
  z-index: 9998;
}

.context-menu {
  position: fixed;
  z-index: 9999;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.15), 0 1px 3px rgba(0, 0, 0, 0.08);
  padding: 6px 0;
  min-width: 200px;
  font-size: 13px;
  line-height: 1;
  user-select: none;
  overflow: hidden;
}

.menu-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.menu-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 28px 0 14px;
  height: 30px;
  cursor: pointer;
  color: #1d1d1d;
  transition: background 0.1s;
  white-space: nowrap;
  margin: 2px 6px;
  border-radius: 5px;
}

.menu-item:hover {
  background: #e8e8e8;
}

.menu-item.menu-active {
  background: #d8d8d8;
  color: #1d1d1d;
}

.menu-item.menu-danger {
  color: #d13438;
}

.menu-item.menu-danger:hover {
  background: #fde7e9;
  color: #d13438;
}

.menu-item.menu-danger.menu-active {
  background: #d13438;
  color: #fff;
}

.menu-item.menu-disabled {
  color: #a0a0a0;
  cursor: default;
}

.menu-item.menu-disabled:hover,
.menu-item.menu-disabled.menu-active {
  background: transparent;
  color: #a0a0a0;
}

.menu-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 400;
}

.menu-arrow {
  font-size: 8px;
  color: #666;
  flex-shrink: 0;
  margin-left: auto;
  transform: scale(0.7);
}

.menu-item:hover .menu-arrow,
.menu-item.menu-active .menu-arrow {
  color: #333;
}

.menu-divider {
  height: 1px;
  background: #e0e0e0;
  margin: 6px 0;
  list-style: none;
}

/* 子菜单 */
.menu-submenu {
  position: absolute;
  left: 100%;
  top: -6px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.15), 0 1px 3px rgba(0, 0, 0, 0.08);
  padding: 6px 0;
  min-width: 180px;
  z-index: 10000;
  overflow: hidden;
}

.menu-nested .menu-item {
  height: 28px;
  font-size: 13px;
  padding: 0 24px 0 14px;
  margin: 2px 6px;
  border-radius: 5px;
}

/* 动画 */
.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.1s ease;
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
}

.menu-fade-enter-to,
.menu-fade-leave-from {
  opacity: 1;
}
</style>

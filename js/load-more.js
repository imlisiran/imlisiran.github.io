// ===== Load More Articles =====

// 加载更多文章的函数
function loadMoreArticles(loadMoreBtn, totalPages) {
  // 获取当前页码（从按钮属性中获取，而不是使用初始化时的值）
  const currentPage = parseInt(loadMoreBtn.getAttribute('data-current-page')) || 1;
  const nextPage = currentPage + 1;

  // 显示加载状态
  const isTagPage = document.querySelector('.post-list') !== null;
  const originalText = loadMoreBtn.innerHTML;

  // 检查是否是滚动加载模式
  const loadMoreMode = typeof theme !== 'undefined' && theme.article_list && theme.article_list.load_more_mode
    ? theme.article_list.load_more_mode
    : 'click';

  // 在滚动加载模式下，按钮始终隐藏
  if (loadMoreMode === 'scroll') {
    loadMoreBtn.style.display = 'none';
  } else {
    loadMoreBtn.innerHTML = '<span class="loading"></span> ' + (isTagPage ? '加载中...' : 'Loading...');
  }

  loadMoreBtn.disabled = true;

  // 保存原始文本，用于恢复
  if (!loadMoreBtn.dataset.originalText) {
    loadMoreBtn.dataset.originalText = originalText;
  }

  // 构建下一页URL
  let currentPath = window.location.pathname;

  // 移除末尾的斜杠，避免重复
  if (currentPath.endsWith('/')) {
    currentPath = currentPath.slice(0, -1);
  }

  // 如果当前路径已经包含/page/x，移除它
  currentPath = currentPath.replace(/\/page\/\d+$/, '');

  // 构建下一页URL
  const nextPageUrl = currentPath + '/page/' + nextPage + '/';

  // 获取下一页内容
  fetch(nextPageUrl)
    .then(response => response.text())
    .then(html => {
      // 创建临时DOM元素来解析HTML
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');

      // 获取新文章
      let newArticles;
      let articlesGrid;

      // 检查是否在标签页面
      const isTagPage = document.querySelector('.post-list') !== null;

      if (isTagPage) {
        // 标签页面使用不同的选择器
        newArticles = doc.querySelectorAll('.post-item');
        articlesGrid = document.querySelector('.post-list');
      } else {
        // 主页使用原有的选择器
        newArticles = doc.querySelectorAll('.article-card');
        articlesGrid = document.querySelector('.articles-grid');
      }

      if (newArticles.length > 0 && articlesGrid) {
        // 获取当前文章数量，用于确定尺寸类
        const currentArticles = isTagPage
          ? articlesGrid.querySelectorAll('.post-item')
          : articlesGrid.querySelectorAll('.article-card');
        const startIndex = currentArticles.length;

        // 获取当前文章的链接，用于检查重复
        const currentArticleLinks = Array.from(currentArticles).map(article => {
          const link = article.querySelector('a[href]');
          return link ? link.getAttribute('href') : '';
        });

        // 创建一个文档片段，减少DOM操作
        const fragment = document.createDocumentFragment();

        // 添加新文章到网格
        newArticles.forEach((article, index) => {
          // 获取新文章的链接
          const newArticleLink = article.querySelector('a[href]');
          const newLink = newArticleLink ? newArticleLink.getAttribute('href') : '';

          // 检查文章是否已经存在
          if (currentArticleLinks.includes(newLink)) {
            return; // 如果文章已存在，跳过此文章
          }

          // 克隆文章元素
          const clonedArticle = article.cloneNode(true);

          // 如果不是标签页面，应用卡片尺寸逻辑
          if (!isTagPage) {
            // 获取当前屏幕宽度，确定列数
            let columns = 4; // 默认4列
            if (window.innerWidth <= 480) columns = 1;
            else if (window.innerWidth <= 768) columns = 2;
            else if (window.innerWidth <= 1200) columns = 3;

            // 移除原有的尺寸类
            clonedArticle.className = clonedArticle.className.replace(/article-card--(large|medium|small|wide|tall)/g, '');

            // 根据位置和列数确定尺寸类
            const positionInRow = (startIndex + index) % columns;
            let sizeClass;

            // 根据列数和位置确定尺寸类
            if (columns === 1) {
              // 单列布局，全部使用medium
              sizeClass = 'article-card--medium';
            } else if (columns === 2) {
              // 双列布局
              if (positionInRow === 0) {
                sizeClass = Math.random() > 0.5 ? 'article-card--large' : 'article-card--tall';
              } else {
                sizeClass = 'article-card--medium';
              }
            } else if (columns === 3) {
              // 三列布局
              if (positionInRow === 0) {
                sizeClass = Math.random() > 0.5 ? 'article-card--wide' : 'article-card--large';
              } else {
                sizeClass = 'article-card--medium';
              }
            } else {
              // 四列布局
              if (positionInRow === 0) {
                sizeClass = 'article-card--large';
              } else if (positionInRow === 1) {
                sizeClass = Math.random() > 0.5 ? 'article-card--tall' : 'article-card--wide';
              } else {
                sizeClass = 'article-card--medium';
              }
            }

            clonedArticle.classList.add(sizeClass);
          }

          // 设置初始透明度用于淡入效果
          clonedArticle.style.opacity = '0';
          clonedArticle.style.transition = 'opacity 0.5s ease';

          // 添加到文档片段
          fragment.appendChild(clonedArticle);
        });

        // 一次性添加所有新文章到网格
        articlesGrid.appendChild(fragment);

        // 触发淡入效果
        setTimeout(() => {
          const newCards = isTagPage
            ? articlesGrid.querySelectorAll('.post-item')
            : articlesGrid.querySelectorAll('.article-card');
          for (let i = startIndex; i < newCards.length; i++) {
            newCards[i].style.opacity = '1';
          }
        }, 10);

        // 触发加载完成事件
        document.dispatchEvent(new Event('loadMoreComplete'));

        // 更新按钮状态
        if (nextPage >= totalPages) {
          loadMoreBtn.innerHTML = isTagPage ? '没有更多文章' : 'No more articles';
          loadMoreBtn.style.opacity = '0.6';
          loadMoreBtn.disabled = true; // 禁用按钮，防止重复点击
        } else {
          // 检查是否是滚动加载模式
          const loadMoreMode = typeof theme !== 'undefined' && theme.article_list && theme.article_list.load_more_mode
            ? theme.article_list.load_more_mode
            : 'click';

          // 在滚动加载模式下，按钮始终隐藏
          if (loadMoreMode === 'scroll') {
            loadMoreBtn.style.display = 'none';
          } else {
            // 恢复按钮文本
            loadMoreBtn.innerHTML = loadMoreBtn.dataset.originalText || (isTagPage ? '加载更多文章' : 'Load More Articles');
          }

          loadMoreBtn.disabled = false;
          loadMoreBtn.setAttribute('data-current-page', nextPage);
        }
      } else {
        // 检查是否是滚动加载模式
        const loadMoreMode = typeof theme !== 'undefined' && theme.article_list && theme.article_list.load_more_mode
          ? theme.article_list.load_more_mode
          : 'click';

        // 在滚动加载模式下，按钮始终隐藏
        if (loadMoreMode === 'scroll') {
          loadMoreBtn.style.display = 'none';
        } else {
          // 恢复按钮文本
          loadMoreBtn.innerHTML = loadMoreBtn.dataset.originalText || (isTagPage ? '没有更多文章' : 'No more articles');
        }

        loadMoreBtn.style.opacity = '0.6';
        loadMoreBtn.disabled = true; // 禁用按钮，防止重复点击
      }
    })
    .catch(error => {
      console.error('Error loading more articles:', error);
      const isTagPage = document.querySelector('.post-list') !== null;

      // 检查是否是滚动加载模式
      const loadMoreMode = typeof theme !== 'undefined' && theme.article_list && theme.article_list.load_more_mode
        ? theme.article_list.load_more_mode
        : 'click';

      // 在滚动加载模式下，按钮始终隐藏
      if (loadMoreMode === 'scroll') {
        loadMoreBtn.style.display = 'none';
      } else {
        loadMoreBtn.innerHTML = isTagPage ? '加载文章出错' : 'Error loading articles';
      }

      loadMoreBtn.style.opacity = '0.6';
      loadMoreBtn.disabled = true; // 禁用按钮，防止重复点击

      // 触发加载完成事件
      document.dispatchEvent(new Event('loadMoreComplete'));
    });
}

// 设置滚动加载功能
function setupScrollLoad(loadMoreBtn, totalPages) {
  let isLoading = false;
  let isEndReached = false;

  // 检查是否滚动到底部
  function checkScrollPosition() {
    if (isLoading || isEndReached) return;

    const scrollPosition = window.innerHeight + window.scrollY;
    const pageHeight = document.body.offsetHeight;

    // 当滚动到距离底部200px时触发加载
    if (scrollPosition >= pageHeight - 200) {
      loadMoreArticles(loadMoreBtn, totalPages);
      isLoading = true;
    }
  }

  // 监听滚动事件
  window.addEventListener('scroll', checkScrollPosition);

  // 监听加载完成事件
  document.addEventListener('loadMoreComplete', function() {
    isLoading = false;

    // 检查是否已经是最后一页
    const currentPage = parseInt(loadMoreBtn.getAttribute('data-current-page')) || 1;
    if (currentPage >= totalPages) {
      isEndReached = true;
      window.removeEventListener('scroll', checkScrollPosition);
    } else {
      // 如果不是最后一页，检查是否需要继续加载
      setTimeout(() => {
        checkScrollPosition();
      }, 100);
    }
  });
}

function initLoadMore() {
  const loadMoreBtn = document.querySelector('.load-more-btn');
  if (!loadMoreBtn) return;

  // 获取当前页码和总页数
  const currentPage = parseInt(loadMoreBtn.getAttribute('data-current-page')) || 1;
  const totalPages = parseInt(loadMoreBtn.getAttribute('data-total-pages')) || 1;

  // 如果已经是最后一页，隐藏按钮
  if (currentPage >= totalPages) {
    loadMoreBtn.style.display = 'none';
    return;
  }

  // 检查配置中的加载方式
  const loadMoreMode = typeof theme !== 'undefined' && theme.article_list && theme.article_list.load_more_mode
    ? theme.article_list.load_more_mode
    : 'click';

  // 如果是滚动加载模式，隐藏按钮并设置滚动监听
  if (loadMoreMode === 'scroll') {
    loadMoreBtn.style.display = 'none';
    setupScrollLoad(loadMoreBtn, totalPages);
  }

  // 点击事件处理
  loadMoreBtn.addEventListener('click', function() {
    loadMoreArticles(this, totalPages);
  });
}

// 当DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', initLoadMore);
